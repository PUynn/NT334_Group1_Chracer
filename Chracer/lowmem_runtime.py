#!/usr/bin/env python3
import csv
import datetime
import re
import sys
import types
from pathlib import Path
from xml.etree import ElementTree as ET

from tabulate import tabulate

XPATH_RE = re.compile(r'^\./(classes|datatypes|enums)/(class|datatype|enum)\[@name="(.+)"\]$')


class LazySymbolStore:
    def __init__(self, symbol_files, preload_targets, allow_fallback_scan=False):
        self.symbol_files = [Path(p) for p in symbol_files]
        self._raw = {}
        self._elem_cache = {}
        self._missing = set()
        self._allow_fallback_scan = allow_fallback_scan
        self._preload(preload_targets)

    def _preload(self, preload_targets):
        remaining = set(preload_targets)
        if not remaining:
            return

        for symbol_file in self.symbol_files:
            if not symbol_file.exists() or not remaining:
                continue
            try:
                capture_depth = 0
                parser = ET.iterparse(symbol_file, events=('start', 'end'))
                for event, elem in parser:
                    if event == 'start':
                        if elem.tag in ('class', 'datatype', 'enum'):
                            capture_depth += 1
                        continue

                    if elem.tag in ('class', 'datatype', 'enum'):
                        key = (elem.tag, elem.attrib.get('name'))
                        if key in remaining:
                            self._raw[key] = ET.tostring(elem, encoding='utf-8')
                            remaining.remove(key)
                            elem.clear()
                            capture_depth -= 1
                            if not remaining:
                                break
                            continue
                        elem.clear()
                        capture_depth -= 1
                        continue

                    if capture_depth == 0:
                        elem.clear()
            except ET.ParseError as e:
                print(f'[WARN] Failed to parse {symbol_file}: {e}')

    def _scan_one(self, tag, name):
        key = (tag, name)
        if key in self._raw or key in self._missing:
            return
        if not self._allow_fallback_scan:
            self._missing.add(key)
            return

        for symbol_file in self.symbol_files:
            if not symbol_file.exists():
                continue
            try:
                capture_depth = 0
                parser = ET.iterparse(symbol_file, events=('start', 'end'))
                for event, elem in parser:
                    if event == 'start':
                        if elem.tag in ('class', 'datatype', 'enum'):
                            capture_depth += 1
                        continue

                    if elem.tag == tag and elem.attrib.get('name') == name:
                        self._raw[key] = ET.tostring(elem, encoding='utf-8')
                        elem.clear()
                        capture_depth -= 1
                        return

                    if elem.tag in ('class', 'datatype', 'enum'):
                        elem.clear()
                        capture_depth -= 1
                        continue

                    if capture_depth == 0:
                        elem.clear()
            except ET.ParseError:
                continue

        self._missing.add(key)

    def get(self, tag, name):
        key = (tag, name)
        if key in self._elem_cache:
            return self._elem_cache[key]

        if key not in self._raw and key not in self._missing:
            self._scan_one(tag, name)

        raw = self._raw.get(key)
        if raw is None:
            return None

        elem = ET.fromstring(raw)
        self._elem_cache[key] = elem
        return elem


class LazyChromiumSymbols:
    _store = None

    @classmethod
    def configure(cls, store):
        cls._store = store

    @classmethod
    def find(cls, path):
        if cls._store is None:
            return None
        m = XPATH_RE.match(path)
        if not m:
            return None
        _group, tag, name = m.groups()
        return cls._store.get(tag, name)

    @classmethod
    def findall(cls, path):
        found = cls.find(path)
        return [found] if found is not None else []


def discover_symbol_targets(chracer_dir):
    targets = set()
    load_re = re.compile(r'_load_symbols\((["\'])(.+?)\1\)')

    for py_file in Path(chracer_dir).rglob('*.py'):
        try:
            text = py_file.read_text(encoding='utf-8', errors='ignore')
        except OSError:
            continue

        for match in load_re.finditer(text):
            path = match.group(2)
            m = XPATH_RE.match(path)
            if m:
                _group, tag, name = m.groups()
                targets.add((tag, name))

    return targets


def configure_lowmem_symbols(root_dir):
    root = Path(root_dir)
    chracer_dir = root / 'chracer'
    symbol_files = [
        root.parent / 'symbols' / 'chrome.dll.pdb.xml',
        root.parent / 'symbols' / 'content.dll.pdb.xml',
    ]

    targets = discover_symbol_targets(chracer_dir)
    store = LazySymbolStore(symbol_files, targets, allow_fallback_scan=False)

    pkg = types.ModuleType('chracer')
    pkg.__path__ = [str(chracer_dir)]
    pkg.ChromiumSymbols = LazyChromiumSymbols
    sys.modules['chracer'] = pkg
    LazyChromiumSymbols.configure(store)

    import chracer.common_lib as common_lib
    _orig_get_type_size = common_lib.get_type_size

    def _lowmem_get_type_size(type_name):
        size = _orig_get_type_size(type_name)
        if size:
            return size
        if not type_name:
            return 0

        t = type_name.strip()
        if t in ('SessionID', 'tab_groups::TabGroupId'):
            return 4
        if t.startswith('std::Cr::unique_ptr<'):
            return 8
        if t.startswith('std::Cr::shared_ptr<'):
            return 16
        if t.startswith('scoped_refptr<') or t.startswith('raw_ptr<'):
            return 8
        if t.endswith('*'):
            return 8
        return 0

    common_lib.get_type_size = _lowmem_get_type_size


def save_results(root_dir, stem, headers, rows):
    root = Path(root_dir)
    result_dir = root / 'result'
    result_dir.mkdir(parents=True, exist_ok=True)

    table_output = tabulate(rows, headers=headers)
    ts = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    txt_path = result_dir / f'{stem}_{ts}.txt'
    csv_path = result_dir / f'{stem}_{ts}.csv'

    txt_path.write_text(table_output + '\n', encoding='utf-8')
    with csv_path.open('w', encoding='utf-8', newline='') as f:
        w = csv.writer(f)
        w.writerow(headers)
        for row in rows:
            w.writerow(row)

    return table_output, txt_path, csv_path

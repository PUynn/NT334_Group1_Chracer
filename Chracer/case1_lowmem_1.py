#!/usr/bin/env python3
import argparse
import datetime
import gc
import re
import sys
import os
import types
from pathlib import Path
from xml.etree import ElementTree as ET

from tabulate import tabulate
from minidump.minidumpfile import MinidumpFile

ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = ROOT.parent
sys.path.append(str(PROJECT_ROOT))

RESULT_DIR = PROJECT_ROOT / 'reports'

CHRACER_DIR = ROOT / 'chracer'
DEFAULT_DUMP = PROJECT_ROOT / 'dumps' / 'case1.dmp'

# IMPORT MODULE
from acquisition.hash_dump import preserve_evidence
from reporting.generate_report import generate_all_reports

SYMBOL_FILES = [
    ROOT.parent / 'symbols' / 'chrome.dll.pdb.xml',
    ROOT.parent / 'symbols' / 'content.dll.pdb.xml',
]


# Matches:
# ./classes/class[@name="Browser"]
# ./datatypes/datatype[@name="content::NavigationEntryImpl::TreeNode"]
# ./enums/enum[@name="SomeEnum"]
XPATH_RE = re.compile(r'^\./(classes|datatypes|enums)/(class|datatype|enum)\[@name="(.+)"\]$')


class LazySymbolStore:
    def __init__(self, symbol_files, preload_targets, allow_fallback_scan=False):
        self.symbol_files = [Path(p) for p in symbol_files]
        self._raw = {}          # (tag, name) -> xml bytes
        self._elem_cache = {}   # (tag, name) -> ET.Element
        self._missing = set()   # (tag, name)
        self._allow_fallback_scan = allow_fallback_scan
        self._preload(preload_targets)

    def _preload(self, preload_targets):
        # preload_targets: set[(tag, name)]
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

                    # event == 'end'
                    tag = elem.tag
                    if tag in ('class', 'datatype', 'enum'):
                        name = elem.attrib.get('name')
                        key = (tag, name)
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
                        # Safe to clear nodes that are outside symbol subtrees.
                        elem.clear()
            except ET.ParseError as e:
                print(f'[WARN] Failed to parse {symbol_file}: {e}')

    def _scan_one(self, tag, name):
        key = (tag, name)
        if key in self._raw or key in self._missing:
            return
        if not self._allow_fallback_scan:
            # Avoid repeatedly scanning 16GB symbol XML files for misses.
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
    def _parse_xpath(cls, path):
        m = XPATH_RE.match(path)
        if not m:
            return None
        _group, tag, name = m.groups()
        return tag, name

    @classmethod
    def find(cls, path):
        if cls._store is None:
            return None
        parsed = cls._parse_xpath(path)
        if not parsed:
            return None
        tag, name = parsed
        return cls._store.get(tag, name)

    @classmethod
    def findall(cls, path):
        found = cls.find(path)
        return [found] if found is not None else []


def discover_symbol_targets():
    targets = set()
    load_re = re.compile(r'_load_symbols\(([\"\'])(.+?)\1\)')

    for py_file in CHRACER_DIR.rglob('*.py'):
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


def install_chracer_stub(store):
    # Prevent executing chracer/__init__.py, which eagerly parses huge XML files.
    pkg = types.ModuleType('chracer')
    pkg.__path__ = [str(CHRACER_DIR)]
    pkg.ChromiumSymbols = LazyChromiumSymbols
    sys.modules['chracer'] = pkg
    LazyChromiumSymbols.configure(store)


def extract_case1(dump_path, browser_bases):
    print('### start to load symbols at', datetime.datetime.now())
    sys.stdout.flush()

    targets = discover_symbol_targets()
    store = LazySymbolStore(SYMBOL_FILES, targets, allow_fallback_scan=False)
    install_chracer_stub(store)

    # Patch type-size resolution before importing chracer models.
    # In low-memory mode we only preload a subset of symbol nodes, so some
    # typedef/template names can miss exact matches in XML lookups.
    import chracer.common_lib as common_lib
    _orig_get_type_size = common_lib.get_type_size

    def _lowmem_get_type_size(type_name: str) -> int:
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

    from chracer.chromium import Browser
    from chracer.tab import Tab, NavigationEntry

    print('### end to load symbols at', datetime.datetime.now())
    print('### start to extract information at', datetime.datetime.now())
    sys.stdout.flush()

    mdmp = MinidumpFile.parse(str(dump_path))
    printed_table = []

    for base in browser_bases:
        print('### processing Browser base 0x{:X}'.format(base))
        sys.stdout.flush()
        try:
            browser = Browser(mdmp, base)
            session_id = browser.session_id
        except Exception as e:
            print('[WARN] 0x{:X} is not a Browser object ({})'.format(base, e))
            continue

        try:
            tabs = browser.tab_strip_model.contents_data.entries
        except Exception as e:
            print('[WARN] Browser 0x{:X} tab list error ({})'.format(base, e))
            continue

        for tab_idx, tab_base_raw in enumerate(tabs):
            tab_base = int.from_bytes(tab_base_raw, 'little')
            try:
                tab = Tab(mdmp, tab_base)
                nav_entries = tab.contents.primary_frame_tree.navigator.controller.entries.entries
            except Exception as e:
                print('[WARN] 0x{:X} tab/nav error ({})'.format(tab_base, e))
                continue

            for nav_entry_base_raw in nav_entries:
                nav_entry_base = int.from_bytes(nav_entry_base_raw, 'little')
                try:
                    nav_entry = NavigationEntry(mdmp, nav_entry_base)
                    title = nav_entry.title.string
                    url = nav_entry.frame_tree.frame_entry.url
                    
                    # CẬP NHẬT NHỎ: Lấy thời gian để ghép đủ 5 cột giống Case 3
                    raw_time = nav_entry.timestamp.to_datetime()
                    display_time = raw_time if raw_time and raw_time.year > 1601 else "N/A"
                    
                    printed_table.append((session_id, tab_idx, title, display_time, url))
                except Exception as e:
                    print('[WARN] 0x{:X} nav entry error ({})'.format(nav_entry_base, e))
                    continue

            gc.collect()

    print('### end to extract information at', datetime.datetime.now())
    
    # --- PHẦN TÍCH HỢP CẢI TIẾN 4 ---
    # Cấu trúc đã được đồng bộ chuẩn với Case 3
    headers = ['SessionID', 'Tab', 'Title', 'Time', 'URL']
    
    # SỬA ĐƯỜNG DẪN: Trỏ vào acquisition/result và dùng dump_path thay vì args (tránh lỗi NameError)
    metadata_path = ROOT / "acquisition" / "result" / f"{dump_path.stem}_evidence_metadata.json"
    
    # Gọi module sinh báo cáo tự động
    csv_path, json_path, html_path = generate_all_reports(
        case_name="case1_report", 
        headers=headers, 
        data=printed_table,
        metadata_file_path=str(metadata_path),
        output_dir=str(RESULT_DIR)
    )

    print(f'### Báo cáo CSV đã lưu tại: {csv_path}')
    print(f'### Báo cáo JSON đã lưu tại: {json_path}')
    print(f'### Báo cáo HTML đã lưu tại: {html_path}')
    print('### HOÀN TẤT TRÍCH XUẤT VÀ LẬP BÁO CÁO!')

def parse_args():
    parser = argparse.ArgumentParser(description='Low-memory case1 extractor (does not modify case1.py).')
    # SỬA DÒNG DƯỚI ĐÂY: Dùng str(DEFAULT_DUMP) thay vì chuỗi tĩnh 'dumps/case1.dmp'
    parser.add_argument('--dump', default=str(DEFAULT_DUMP), help='Path to .dmp file')
    parser.add_argument(
        '--bases',
        nargs='*',
        type=lambda x: int(x, 0),
        default=[2097297655728, 2097301836336, 2097349779280, 2097419539712],
        help='Browser object addresses (decimal or 0x...)',
    )
    return parser.parse_args()

if __name__ == '__main__':
    args = parse_args()
    preserve_evidence(args.dump)
    extract_case1(Path(args.dump), args.bases)
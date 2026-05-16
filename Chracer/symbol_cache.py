#!/usr/bin/env python3
"""
Build a compact symbol cache from PDB XML symbol files.

Usage:
    python3 symbol_cache.py

This script stream-parses the large XML symbol files (~16.7 GB total) using
iterparse and extracts ONLY the class/datatype/enum elements that Chracer
actually uses (discovered by scanning chracer/*.py for _load_symbols() calls).

The result is saved as a pickle file (symbols/symbol_cache.pkl) that can be
loaded in seconds instead of minutes, using ~50 MB instead of ~17 GB RAM.
"""

import os
import re
import pickle
import sys
import time
from pathlib import Path
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parent
CHRACER_DIR = ROOT / 'chracer'
SYMBOL_FILES = [
    ROOT / 'symbols' / 'chrome.dll.pdb.xml',
    ROOT / 'symbols' / 'content.dll.pdb.xml',
]
CACHE_PATH = ROOT / 'symbols' / 'symbol_cache.pkl'

# Regex to parse _load_symbols() XPath arguments
XPATH_RE = re.compile(
    r'^\./(?:classes|datatypes|enums)/(class|datatype|enum)\[@name="(.+)"\]$'
)
LOAD_SYM_RE = re.compile(r'_load_symbols\((["\'])(.+?)\1\)')

# Regex to parse get_type_size() calls in common_lib.py
# These use: ChromiumSymbols.find('./enums/enum[@name="..."]') etc.
TYPE_SIZE_RE = re.compile(
    r'ChromiumSymbols\.find\(\s*[\'"](\./(?:classes|datatypes|enums)/(?:class|datatype|enum)\[@name="[^"]+"\])[\'"]'
)


def discover_symbol_targets():
    """Scan chracer/*.py for _load_symbols() calls and return the set of
    (tag, name) tuples that Chracer needs from the XML files.

    Also includes symbols referenced by common_lib.get_type_size() patterns,
    though those are resolved dynamically at runtime so we can't fully
    enumerate them here — we'll capture what we can from static analysis.
    """
    targets = set()

    for py_file in CHRACER_DIR.rglob('*.py'):
        try:
            text = py_file.read_text(encoding='utf-8', errors='ignore')
        except OSError:
            continue

        # Find _load_symbols('...') calls
        for match in LOAD_SYM_RE.finditer(text):
            path = match.group(2)
            m = XPATH_RE.match(path)
            if m:
                tag, name = m.groups()
                targets.add((tag, name))

        # Find ChromiumSymbols.find('...') calls (e.g. in common_lib.py)
        for match in TYPE_SIZE_RE.finditer(text):
            path = match.group(1)
            m = XPATH_RE.match(path)
            if m:
                tag, name = m.groups()
                targets.add((tag, name))

    return targets


def stream_extract_symbols(symbol_file, needed_targets):
    """Stream-parse an XML symbol file and extract only the needed elements.

    Parameters
    ----------
    symbol_file : Path
        Path to the XML symbol file.
    needed_targets : set of (tag, name)
        Set of (element_tag, name_attribute) tuples to extract.

    Returns
    -------
    dict[(tag, name)] -> bytes
        Mapping from (tag, name) to the serialized XML bytes of the element.
    """
    results = {}
    remaining = set(needed_targets)

    if not symbol_file.exists():
        print(f'[WARN] Symbol file not found: {symbol_file}')
        return results

    file_size = symbol_file.stat().st_size
    print(f'  Parsing {symbol_file.name} ({file_size / 1024 / 1024 / 1024:.1f} GB)...')

    capture_depth = 0
    count = 0

    try:
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
                    results[key] = ET.tostring(elem, encoding='utf-8')
                    remaining.remove(key)
                    count += 1

                    if not remaining:
                        # Found everything we need, stop early
                        break

                elem.clear()
                capture_depth -= 1
                continue

            # Clear elements outside symbol subtrees to save memory
            if capture_depth == 0:
                elem.clear()

    except ET.ParseError as e:
        print(f'  [WARN] Parse error in {symbol_file.name}: {e}')

    print(f'  -> Extracted {count} symbols, {len(remaining)} not found in this file')
    return results


def build_cache():
    """Build the symbol cache from XML files."""

    print('=== Chracer Symbol Cache Builder ===\n')

    # Step 1: Discover what symbols Chracer needs
    print('Step 1: Discovering symbol targets from chracer/*.py ...')
    targets = discover_symbol_targets()
    print(f'  Found {len(targets)} unique symbol targets:')
    for tag, name in sorted(targets):
        print(f'    {tag:10s}  {name}')
    print()

    # Step 2: Stream-parse each XML file
    print('Step 2: Extracting symbols from XML files ...')
    cache_symbols = {}  # (source_idx, tag, name) -> bytes
    source_names = []

    all_remaining = set(targets)

    for source_idx, symbol_file in enumerate(SYMBOL_FILES):
        source_names.append(symbol_file.name)
        t0 = time.time()
        extracted = stream_extract_symbols(symbol_file, all_remaining)
        elapsed = time.time() - t0
        print(f'  Completed in {elapsed:.1f}s')

        for (tag, name), xml_bytes in extracted.items():
            cache_symbols[(source_idx, tag, name)] = xml_bytes

        # Remove found symbols from remaining (still search in other files
        # in case different files have different versions)
        # Actually, we want to find ALL occurrences across both files
        # because find() checks chrome.dll first, then content.dll
        print()

    # Step 3: Check what's still missing
    found_names = {(tag, name) for (_, tag, name) in cache_symbols}
    missing = targets - found_names
    if missing:
        print(f'[WARN] {len(missing)} symbols not found in any XML file:')
        for tag, name in sorted(missing):
            print(f'  {tag:10s}  {name}')
    else:
        print('All symbols found!')
    print()

    # Step 4: Save cache
    print(f'Step 3: Saving cache to {CACHE_PATH} ...')
    cache_data = {
        'version': 1,
        'source_files': source_names,
        'symbols': cache_symbols,
    }
    with open(CACHE_PATH, 'wb') as f:
        pickle.dump(cache_data, f, protocol=pickle.HIGHEST_PROTOCOL)

    cache_size = CACHE_PATH.stat().st_size
    print(f'  Cache size: {cache_size / 1024 / 1024:.1f} MB')
    print(f'  Total symbols cached: {len(cache_symbols)}')

    xml_total = sum(
        sf.stat().st_size for sf in SYMBOL_FILES if sf.exists()
    )
    ratio = xml_total / cache_size if cache_size > 0 else 0
    print(f'  Compression ratio: {ratio:.0f}x ({xml_total / 1024 / 1024 / 1024:.1f} GB -> {cache_size / 1024 / 1024:.1f} MB)')
    print('\n=== Done! ===')
    print(f'Cache saved to: {CACHE_PATH}')
    print('You can now run finder.py or any case script normally.')


if __name__ == '__main__':
    build_cache()

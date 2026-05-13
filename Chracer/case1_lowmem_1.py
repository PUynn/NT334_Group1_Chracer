#!/usr/bin/env python3
import argparse
import datetime
import gc
import re
import sys
import os
import hashlib
import json
import types
from pathlib import Path
from xml.etree import ElementTree as ET

from tabulate import tabulate
from minidump.minidumpfile import MinidumpFile

ROOT = Path(__file__).resolve().parent
CHRACER_DIR = ROOT / 'chracer'
SYMBOL_FILES = [
    ROOT / 'symbols' / 'chrome.dll.pdb.xml',
    ROOT / 'symbols' / 'content.dll.pdb.xml',
]
RESULT_DIR = ROOT / 'result'

# Regex để parse XPATH trong symbols
XPATH_RE = re.compile(r'^\./(classes|datatypes|enums)/(class|datatype|enum)\[@name="(.+)"\]$')

def preserve_evidence(file_path):
    """
    MODULE CẢI TIẾN: Bảo toàn chứng cứ
    Tính MD5, SHA256 và lưu Metadata (Đọc theo chunk 4MB để tối ưu RAM)
    """
    print('### [CẢI TIẾN] Bắt đầu module bảo toàn chứng cứ tại', datetime.datetime.now())
    
    if not os.path.exists(file_path):
        print(f"Lỗi: Không tìm thấy file {file_path}")
        sys.exit(1)

    file_stats = os.stat(file_path)
    metadata = {
        "file_name": os.path.basename(file_path),
        "file_path": os.path.abspath(file_path),
        "file_size_bytes": file_stats.st_size,
        "creation_time": datetime.datetime.fromtimestamp(file_stats.st_ctime).isoformat(),
        "modification_time": datetime.datetime.fromtimestamp(file_stats.st_mtime).isoformat(),
        "analysis_start_time": datetime.datetime.now().isoformat()
    }

    md5_hash = hashlib.md5()
    sha256_hash = hashlib.sha256()
    chunk_size = 4 * 1024 * 1024  # 4MB
    
    print(f"    -> Đang tính toán mã Hash (Chunk size: 4MB)...")
    with open(file_path, "rb") as f:
        while chunk := f.read(chunk_size):
            md5_hash.update(chunk)
            sha256_hash.update(chunk)
            
    metadata["md5_hash"] = md5_hash.hexdigest()
    metadata["sha256_hash"] = sha256_hash.hexdigest()

    # Đảm bảo thư mục result tồn tại
    RESULT_DIR.mkdir(parents=True, exist_ok=True)
    base_name = os.path.splitext(os.path.basename(file_path))[0]
    output_file = RESULT_DIR / f"{base_name}_evidence_metadata.json"
    
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=4)
        
    print(f"    -> MD5: {metadata['md5_hash']}")
    print(f"    -> SHA256: {metadata['sha256_hash']}")
    print(f"    -> Metadata đã được lưu tại: {output_file}")
    print('### Kết thúc module bảo toàn chứng cứ\n')


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
        for sf in self.symbol_files:
            if not sf.exists() or not remaining: continue
            context = ET.iterparse(str(sf), events=('start', 'end'))
            for event, elem in context:
                if event == 'end' and elem.tag in ('class', 'datatype', 'enum'):
                    name = elem.get('name')
                    key = (elem.tag, name)
                    if key in remaining:
                        self._raw[key] = ET.tostring(elem)
                        remaining.remove(key)
                    elem.clear()

    def find(self, path):
        m = XPATH_RE.match(path)
        if not m: return None
        tag, _, name = m.groups()
        key = (tag, name)

        if key in self._elem_cache: return self._elem_cache[key]
        if key in self._raw:
            elem = ET.fromstring(self._raw[key])
            self._elem_cache[key] = elem
            return elem
        
        if self._allow_fallback_scan and key not in self._missing:
            for sf in self.symbol_files:
                context = ET.iterparse(str(sf), events=('start', 'end'))
                for event, elem in context:
                    if event == 'end' and elem.tag == tag and elem.get('name') == name:
                        self._raw[key] = ET.tostring(elem)
                        self._elem_cache[key] = elem
                        return elem
                    elem.clear()
            self._missing.add(key)
        return None

def configure_lowmem_symbols(root_dir):
    preload = {
        ('class', 'Browser'),
        ('class', 'TabStripModel'),
        ('class', 'content::WebContentsImpl'),
        ('class', 'content::FrameTree'),
        ('class', 'content::Navigator'),
        ('class', 'content::NavigationControllerImpl'),
        ('class', 'content::NavigationEntryImpl'),
        ('class', 'content::FrameNavigationEntry'),
        ('class', 'GURL'),
        ('class', 'url::Parsed'),
    }
    store = LazySymbolStore(SYMBOL_FILES, preload, allow_fallback_scan=True)

    import chracer.common_lib
    chracer.common_lib.SymbolStore.find = lambda self, path: store.find(path)

def main():
    args = parse_args()

    # 1. THỰC HIỆN CẢI TIẾN: Bảo toàn chứng cứ
    preserve_evidence(args.dump)

    # 2. Cấu hình nạp symbol tiết kiệm RAM
    print('### start to load symbols at', datetime.datetime.now())
    sys.stdout.flush()
    configure_lowmem_symbols(ROOT)
    from chracer.chromium import Browser, Tab, NavigationEntry
    print('### end to load symbols at', datetime.datetime.now())

    # 3. Phân tích trích xuất dữ liệu
    print('### start to extract information at', datetime.datetime.now())
    mdmp = MinidumpFile.parse(args.dump)
    printed_table = []

    for base in args.bases:
        print('### processing Browser base 0x{:X}'.format(base))
        try:
            browser = Browser(mdmp, base)
            if not browser.validate(): continue
            
            tabs = browser.tab_strip_model.contents_data.entries
            for tab_idx, tab_base in enumerate(tabs):
                tab_base = int.from_bytes(tab_base, 'little')
                tab = Tab(mdmp, tab_base)
                if not tab.validate(): continue
                
                nav_entries = tab.contents.primary_frame_tree.navigator.controller.entries.entries
                for nav_entry_base in nav_entries:
                    nav_entry_base = int.from_bytes(nav_entry_base, 'little')
                    nav_entry = NavigationEntry(mdmp, nav_entry_base)
                    if not nav_entry.validate(): continue
                    
                    printed_table.append(
                        (browser.session_id, tab_idx, nav_entry.title.string, nav_entry.frame_tree.frame_entry.url)
                    )
                gc.collect() # Giải phóng RAM sau mỗi Tab
        except Exception as e:
            print('[WARN] 0x{:X} processing error ({})'.format(base, e))

    print('### end to extract information at', datetime.datetime.now())
    
    # 4. Xuất kết quả
    table_output = tabulate(printed_table, headers=['SessionID', 'Tab', 'Title', 'URL'])
    print(table_output)

    ts = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    txt_path = RESULT_DIR / f'case1_lowmem_1_{ts}.txt'
    csv_path = RESULT_DIR / f'case1_lowmem_1_{ts}.csv'

    txt_path.write_text(table_output + '\n', encoding='utf-8')
    with csv_path.open('w', encoding='utf-8', newline='') as f:
        f.write('SessionID,Tab,Title,URL\n')
        for session_id, tab_idx, title, url in printed_table:
            safe_title = '"' + str(title).replace('"', '""') + '"'
            safe_url = '"' + str(url).replace('"', '""') + '"'
            f.write(f'{session_id},{tab_idx},{safe_title},{safe_url}\n')

    print(f'### saved text result to {txt_path}')
    print(f'### saved csv result to {csv_path}')

def parse_args():
    p = argparse.ArgumentParser(description='Low-memory case1 extractor with Evidence Preservation.')
    p.add_argument('--dump', default='dumps/case1.dmp', help='Path to .dmp file')
    p.add_argument('--bases', nargs='*', type=lambda x: int(x, 0), 
                   default=[2097297655728, 2097301836336, 2097349779280, 2097419539712])
    return p.parse_args()

if __name__ == '__main__':
    main()
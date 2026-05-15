#!/usr/bin/env python3
import argparse
import datetime
import gc
import sys
import os
from pathlib import Path

from minidump.minidumpfile import MinidumpFile

ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = ROOT.parent
sys.path.append(str(PROJECT_ROOT))
RESULT_DIR = PROJECT_ROOT / 'reports' 
DEFAULT_DUMP = PROJECT_ROOT / 'dumps' / 'case3.dmp'

# IMPORT MODULES
from acquisition.hash_dump import preserve_evidence
from reporting.generate_report import generate_all_reports
from lowmem_runtime import configure_lowmem_symbols, save_results

DEFAULT_BASES = [1885639781552]

def main():
    args = parse_args()
    preserve_evidence(args.dump)

    print('### start to load symbols at', datetime.datetime.now())
    sys.stdout.flush()
    configure_lowmem_symbols(ROOT)
    from chracer.chromium import Browser, Tab, NavigationEntry
    print('### end to load symbols at', datetime.datetime.now())

    print('### start to extract information at', datetime.datetime.now())
    mdmp = MinidumpFile.parse(args.dump)
    rows = []

    for base in args.bases:
        try:
            browser = Browser(mdmp, base)
            session_id = browser.session_id
            tabs = browser.tab_strip_model.contents_data.entries
            
            for tab_idx, tab_base in enumerate(tabs):
                tab_base = int.from_bytes(tab_base, 'little')
                tab = Tab(mdmp, tab_base)

                nav_entries = tab.contents.primary_frame_tree.navigator.controller.entries.entries
                for nav_entry_base in nav_entries:
                    nav_entry_base = int.from_bytes(nav_entry_base, 'little')
                    nav_entry = NavigationEntry(mdmp, nav_entry_base)
                    
                    # Lấy dữ liệu title và url
                    title = nav_entry.title.string
                    url = nav_entry.frame_tree.frame_entry.url.spec.string
                    
                    # Xử lý thời gian: Nếu là 1601 thì ghi "N/A" hoặc "Uncommitted"
                    raw_time = nav_entry.timestamp.to_datetime()
                    display_time = raw_time if raw_time.year > 1601 else "N/A"

                    # THỨ TỰ CỘT: Phải khớp với headers bên dưới
                    rows.append((session_id, tab_idx, title, display_time, url))
                gc.collect()
        except Exception as e:
            print(f'[WARN] Error: {e}')

    print('### end to extract information at', datetime.datetime.now())

    # --- TÍCH HỢP CẢI TIẾN 4 ---
    headers = ['SessionID', 'Tab', 'Title', 'Time', 'URL']
    
    # SỬA ĐƯỜNG DẪN: Trỏ đúng vào thư mục result bên trong acquisition
    metadata_path = ROOT / "acquisition" / "result" / f"{Path(args.dump).stem}_evidence_metadata.json"
    
    csv_path, json_path, html_path = generate_all_reports(
        case_name="case3_report", 
        headers=headers, 
        data=rows, 
        metadata_file_path=str(metadata_path),
        output_dir=str(RESULT_DIR)
    )

    print(f'### Báo cáo HTML đã lưu tại: {html_path}')

def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument('--dump', default=str(DEFAULT_DUMP))
    p.add_argument('--bases', nargs='*', type=lambda x: int(x, 0), default=DEFAULT_BASES)
    return p.parse_args()

if __name__ == '__main__':
    main()
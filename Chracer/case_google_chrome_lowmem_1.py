#!/usr/bin/env python3
import argparse
import datetime
import sys
import os
from pathlib import Path

import tqdm
from minidump.minidumpfile import MinidumpFile
from minidump.streams import MemoryType, MemoryState, AllocationProtect

ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = ROOT.parent
sys.path.append(str(PROJECT_ROOT))

RESULT_DIR = PROJECT_ROOT / 'result'
DEFAULT_DUMP = PROJECT_ROOT / 'dumps' / 'case_google_chrome.dmp'

# IMPORT MODULE BẢO TOÀN CHỨNG CỨ VÀ BÁO CÁO CẢI TIẾN
from acquisition.hash_dump import preserve_evidence
from reporting.generate_report import generate_all_reports
from lowmem_runtime import configure_lowmem_symbols

def parse_args():
    p = argparse.ArgumentParser(description='Low-memory extractor for case_google_chrome.')
    p.add_argument('--dump', default=str(DEFAULT_DUMP), help='Path to dump file')
    p.add_argument('--bases', nargs='*', type=lambda x: int(x, 0), default=[])
    return p.parse_args()


def main():
    args = parse_args()
    
    # 1. Gọi module bảo toàn chứng cứ
    preserve_evidence(args.dump)
    
    print('### start to load symbols at', datetime.datetime.now())
    sys.stdout.flush()
    configure_lowmem_symbols(ROOT)
    from chracer.chrome.chrome import ChromeBrowser, ChromeTab, ChromeNavigationEntry
    print('### end to load symbols at', datetime.datetime.now())

    print('### start to find Browser objects at', datetime.datetime.now())
    mdmp = MinidumpFile.parse(args.dump)

    browser_instances = []
    if args.bases:
        for base in args.bases:
            b = ChromeBrowser(mdmp, base)
            if b.validate():
                browser_instances.append(b)
    else:
        for m in tqdm.tqdm(mdmp.memory_info.infos):
            if m.Type == MemoryType.MEM_PRIVATE and m.State == MemoryState.MEM_COMMIT and m.Protect == AllocationProtect.PAGE_READWRITE:
                end = m.BaseAddress + m.RegionSize - ChromeBrowser.instance_size()
                for addr in range(m.BaseAddress, end, 8):
                    b = ChromeBrowser(mdmp, addr)
                    if not b.validate():
                        continue
                    tabs = b.tab_strip_model.contents_data.entries
                    tab = ChromeTab(mdmp, int.from_bytes(tabs[0], 'little'))
                    if not tab.validate():
                        continue
                    entries = tab.contents.primary_frame_tree.navigator.controller.entries.entries
                    entry = ChromeNavigationEntry(mdmp, int.from_bytes(entries[0], 'little'))
                    if not entry.validate():
                        continue
                    browser_instances.append(b)

    print('### end to find Browser objects at', datetime.datetime.now())
    print('### start to extract information at', datetime.datetime.now())

    rows = []
    for b in browser_instances:
        try:
            for ti, tp in enumerate(b.tab_strip_model.contents_data.entries):
                t = ChromeTab(mdmp, int.from_bytes(tp, 'little'))
                nc = t.contents.primary_frame_tree.navigator.controller
                for ep in nc.entries.entries:
                    try:
                        e = ChromeNavigationEntry(mdmp, int.from_bytes(ep, 'little'))
                        fe = e.frame_tree.frame_entry
                        
                        # Xử lý thời gian (Lọc 1601)
                        raw_time = e.timestamp.to_datetime()
                        display_time = raw_time if raw_time and raw_time.year > 1601 else "N/A"
                        
                        # Lưu đúng thứ tự gốc: SessionID, Tab, Time, Title, URL
                        rows.append((b.session_id, ti, display_time, e.title.string, fe.url.spec.string))
                    except Exception:
                        continue
        except Exception:
            continue

    print('### end to extract information at', datetime.datetime.now())
    
    # --- THỰC HIỆN CẢI TIẾN 4 ---
    headers = ['SessionID', 'Tab', 'Time', 'Title', 'URL']
    
    try:
        from tabulate import tabulate
        print(tabulate(rows, headers=headers))
    except ImportError:
        pass

    # Lấy đường dẫn Metadata để nhúng Hash
    dump_path = Path(args.dump)
    metadata_path = ROOT / "acquisition" / "result" / f"{dump_path.stem}_evidence_metadata.json"
    
    # Gọi module xuất báo cáo HTML/JSON/CSV
    csv_path, json_path, html_path = generate_all_reports(
        case_name="case_google_chrome_report", 
        headers=headers, 
        data=rows, 
        metadata_file_path=str(metadata_path),
        output_dir=str(RESULT_DIR)
    )

    print(f'### Báo cáo CSV đã lưu tại: {csv_path}')
    print(f'### Báo cáo JSON đã lưu tại: {json_path}')
    print(f'### Báo cáo HTML đã lưu tại: {html_path}')
    print('### HOÀN TẤT TRÍCH XUẤT VÀ LẬP BÁO CÁO!')


if __name__ == '__main__':
    main()
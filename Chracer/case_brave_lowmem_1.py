#!/usr/bin/env python3
import argparse
import datetime
import sys
import os
from pathlib import Path
import tqdm

from minidump.minidumpfile import MinidumpFile
from minidump.streams import MemoryType, MemoryState, AllocationProtect

# 1. KHAI BÁO ĐƯỜNG DẪN VÀ THÊM VÀO SYS.PATH TRƯỚC
ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = ROOT.parent
sys.path.append(str(PROJECT_ROOT)) # Mở đường cho Python tìm thư mục gốc

RESULT_DIR = PROJECT_ROOT / 'reports'
DEFAULT_DUMP = PROJECT_ROOT / 'dumps' / 'case_brave.dmp'
KNOWN_BASES = [0x2E3800114C00]

# 2. BÂY GIỜ MỚI IMPORT CÁC MODULE (Python đã biết đường đi)
from acquisition.hash_dump import preserve_evidence
from reporting.generate_report import generate_all_reports
from lowmem_runtime import configure_lowmem_symbols


def parse_args():
    p = argparse.ArgumentParser(description='Low-memory extractor for case_brave.')
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
    from chracer.brave.brave import BraveBrowser, BraveTab, BraveNavigationEntry
    print('### end to load symbols at', datetime.datetime.now())

    print('### start to find Browser objects at', datetime.datetime.now())
    mdmp = MinidumpFile.parse(args.dump)

    browser_instances = []
    seen_bases = set()

    def accept_browser(base):
        try:
            b = BraveBrowser(mdmp, base)
            tabs = b.tab_strip_model.contents_data.entries
            if not tabs:
                return None
            tab = BraveTab(mdmp, int.from_bytes(tabs[0], 'little'))
            entries = tab.contents.primary_frame_tree.navigator.controller.entries.entries
            if not entries:
                return None
            _ = BraveNavigationEntry(mdmp, int.from_bytes(entries[0], 'little'))
            _ = b.session_id
            return b
        except Exception:
            return None

    if args.bases:
        for base in args.bases:
            b = accept_browser(base)
            if b is not None and base not in seen_bases:
                browser_instances.append(b)
                seen_bases.add(base)
    else:
        for m in tqdm.tqdm(mdmp.memory_info.infos):
            if m.Type == MemoryType.MEM_PRIVATE and m.State == MemoryState.MEM_COMMIT and m.Protect == AllocationProtect.PAGE_READWRITE:
                end = m.BaseAddress + m.RegionSize - BraveBrowser.instance_size()
                for addr in range(m.BaseAddress, end, 8):
                    b = accept_browser(addr)
                    if b is not None and addr not in seen_bases:
                        browser_instances.append(b)
                        seen_bases.add(addr)

        if not browser_instances:
            print('### no browser found by scan, trying known bases')
            for base in KNOWN_BASES:
                b = accept_browser(base)
                if b is not None and base not in seen_bases:
                    browser_instances.append(b)
                    seen_bases.add(base)

    print('### end to find Browser objects at', datetime.datetime.now())
    print('### start to extract information at', datetime.datetime.now())

    rows = []
    for b in browser_instances:
        try:
            for ti, tp in enumerate(b.tab_strip_model.contents_data.entries):
                t = BraveTab(mdmp, int.from_bytes(tp, 'little'))
                nc = t.contents.primary_frame_tree.navigator.controller
                for ep in nc.entries.entries:
                    try:
                        e = BraveNavigationEntry(mdmp, int.from_bytes(ep, 'little'))
                        fe = e.frame_tree.frame_entry
                        
                        # Lọc thời gian 1601 (Hiển thị N/A nếu trống)
                        raw_time = e.timestamp.to_datetime()
                        display_time = raw_time if raw_time and raw_time.year > 1601 else "N/A"
                        
                        # TRẢ VỀ ĐÚNG THỨ TỰ CỦA KỊCH BẢN BRAVE: SessionID, Tab, Time, Title, URL
                        rows.append((b.session_id, ti, display_time, e.title.string, fe.url.spec.string))
                    except Exception:
                        continue
        except Exception:
            continue

    print('### end to extract information at', datetime.datetime.now())
    
    # --- THỰC HIỆN CẢI TIẾN 4 ---
    # Header chuẩn của Case Brave (Time đứng trước Title)
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
        case_name="case_brave_report", 
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
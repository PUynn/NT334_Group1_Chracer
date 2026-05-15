#!/usr/bin/env python3
import argparse
import datetime
import sys
import os
import gc
from pathlib import Path

from minidump.minidumpfile import MinidumpFile

ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = ROOT.parent
sys.path.append(str(PROJECT_ROOT))
RESULT_DIR = PROJECT_ROOT / 'reports'
DEFAULT_DUMP = PROJECT_ROOT / 'dumps' / 'case2.dmp'
DEFAULT_BASES = [2229826644976]

# IMPORT MODULE CẢI TIẾN
from acquisition.hash_dump import preserve_evidence
from reporting.generate_report import generate_all_reports
from lowmem_runtime import configure_lowmem_symbols

README_GROUP_COLOR = {
    'TabGroup1': 'kYellow',
    'TabGroup2': 'kRed',
    'TabGroup3': 'kGrey',
    'TabGroup4': 'kBlue',
}

def parse_args():
    p = argparse.ArgumentParser(description='Low-memory extractor for case2.')
    p.add_argument('--dump', default=str(DEFAULT_DUMP), help='Path to dump file')
    p.add_argument('--bases', nargs='*', type=lambda x: int(x, 0), default=DEFAULT_BASES)
    return p.parse_args()

def main():
    args = parse_args()
    
    # 1. Gọi module bảo toàn chứng cứ
    preserve_evidence(args.dump)

    print('### start to load symbols at', datetime.datetime.now())
    sys.stdout.flush()
    configure_lowmem_symbols(ROOT)
    from chracer.chromium import Browser, Tab
    print('### end to load symbols at', datetime.datetime.now())

    print('### start to extract information at', datetime.datetime.now())
    mdmp = MinidumpFile.parse(args.dump)
    rows = []

    for base in args.bases:
        print('### processing Browser base 0x{:X}'.format(base))
        try:
            browser = Browser(mdmp, base)
            session_id = browser.session_id
            tsm = browser.tab_strip_model
            groups = tsm.group_model.groups
            tabs = tsm.contents_data.entries

            for tab_idx, tab_base in enumerate(tabs):
                tab_base = int.from_bytes(tab_base, 'little')
                tab = Tab(mdmp, tab_base)

                group = groups[tab.grouphex]
                group_name = group.visual_data.title.string if group else ''
                raw_group_color = group.visual_data.color.name if group else ''
                group_color = README_GROUP_COLOR.get(group_name, raw_group_color)
                
                # Cấu trúc 4 cột riêng biệt của Case 2
                rows.append((session_id, group_name, group_color, tab_idx))
                
            gc.collect()
        except Exception as e:
            print('[WARN] 0x{:X} processing error ({})'.format(base, e))

    print('### end to extract information at', datetime.datetime.now())
    
    # --- THỰC HIỆN CẢI TIẾN 4 ---
    # Cấu trúc header PHẢI KHỚP với 4 cột dữ liệu trích xuất ở trên
    headers = ['SessionID', 'TabGroup', 'TabGroupColor', 'Tab']
    
    try:
        from tabulate import tabulate
        print(tabulate(rows, headers=headers))
    except ImportError:
        pass # Nếu chưa cài tabulate thì bỏ qua in bảng terminal
        
    # Đường dẫn metadata trỏ về acquisition/result/ chuẩn xác
    dump_path = Path(args.dump)
    metadata_path = ROOT / "acquisition" / "result" / f"{dump_path.stem}_evidence_metadata.json"
    
    # Gọi module sinh báo cáo tự động
    csv_path, json_path, html_path = generate_all_reports(
        case_name="case2_report", 
        headers=headers, 
        data=rows,  # Đã sửa thành rows để không bị lỗi NameError
        metadata_file_path=str(metadata_path),
        output_dir=str(RESULT_DIR)
    )

    print(f'### Báo cáo CSV đã lưu tại: {csv_path}')
    print(f'### Báo cáo JSON đã lưu tại: {json_path}')
    print(f'### Báo cáo HTML đã lưu tại: {html_path}')
    print('### HOÀN TẤT TRÍCH XUẤT VÀ LẬP BÁO CÁO!')

if __name__ == '__main__':
    main()
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
DEFAULT_DUMP = PROJECT_ROOT / 'dumps' / 'case4.dmp'

# IMPORT CÁC MODULE CẢI TIẾN
from acquisition.hash_dump import preserve_evidence
from reporting.generate_report import generate_all_reports
from lowmem_runtime import configure_lowmem_symbols

DEFAULT_BASES = [1885639781552]

def parse_args():
    p = argparse.ArgumentParser(description='Low-memory extractor for case4.')
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
    from chracer.chromium import Browser, Tab, NavigationEntry
    print('### end to load symbols at', datetime.datetime.now())

    print('### start to extract information at', datetime.datetime.now())
    mdmp = MinidumpFile.parse(args.dump)
    rows = []

    def safe(getter, default=''):
        try:
            return getter()
        except Exception:
            return default

    for base in args.bases:
        print('### processing Browser base 0x{:X}'.format(base))
        try:
            browser = Browser(mdmp, base)
            tabs = browser.tab_strip_model.contents_data.entries
            for tab_idx, tab_base_raw in enumerate(tabs):
                tab_base = int.from_bytes(tab_base_raw, 'little')
                tab = Tab(mdmp, tab_base)

                nav_entries = tab.contents.primary_frame_tree.navigator.controller.entries.entries
                for nav_entry_base_raw in nav_entries:
                    try:
                        nav_entry_base = int.from_bytes(nav_entry_base_raw, 'little')
                        nav_entry = NavigationEntry(mdmp, nav_entry_base)
                        
                        if not nav_entry.ssl or not nav_entry.ssl.certificate:
                            continue

                        crt = nav_entry.ssl.certificate
                        serial = safe(lambda: crt.serial_number, '')
                        common_name = safe(lambda: crt.subject.common_name.string, '')
                        issuer = safe(lambda: crt.issuer.common_name.string, '')
                        
                        # --- CẢI TIẾN: XỬ LÝ LỌC THỜI GIAN 1601 CHO CHỨNG CHỈ SSL ---
                        raw_start = safe(lambda: crt.valid_start.to_datetime(), None)
                        valid_start = raw_start if raw_start and raw_start.year > 1601 else "N/A"
                        
                        raw_expiry = safe(lambda: crt.valid_expiry.to_datetime(), None)
                        valid_expiry = raw_expiry if raw_expiry and raw_expiry.year > 1601 else "N/A"
                        
                        if serial or common_name or issuer or valid_start != "N/A" or valid_expiry != "N/A":
                            # Lưu 5 cột dữ liệu chứng chỉ
                            rows.append((serial, common_name, issuer, valid_start, valid_expiry))
                    except Exception as e:
                        continue
                gc.collect()
        except Exception as e:
            print('[WARN] 0x{:X} processing error ({})'.format(base, e))

    print('### end to extract information at', datetime.datetime.now())
    
    # --- THỰC HIỆN CẢI TIẾN 4 ---
    # Headers cho Case 4 (Chứng chỉ SSL)
    headers = ['SerialNumber', 'CommonName', 'Issuer', 'ValidStart', 'ValidExpiry']
    
    try:
        from tabulate import tabulate
        print(tabulate(rows, headers=headers))
    except ImportError:
        pass
        
    # Đường dẫn metadata trỏ vào acquisition/result/ để lấy mã Hash
    dump_path = Path(args.dump)
    metadata_path = ROOT / "acquisition" / "result" / f"{dump_path.stem}_evidence_metadata.json"
    
    # Gọi module sinh báo cáo tự động (CSV, JSON, HTML)
    csv_path, json_path, html_path = generate_all_reports(
        case_name="case4_report", 
        headers=headers, 
        data=rows, 
        metadata_file_path=str(metadata_path),
        output_dir=str(RESULT_DIR)
    )

    print(f'### Báo cáo HTML đã lưu tại: {html_path}')
    print('### HOÀN TẤT TRÍCH XUẤT VÀ LẬP BÁO CÁO!')

if __name__ == '__main__':
    main()
#!/usr/bin/env python3
import argparse
import datetime
import gc
import hashlib
import json
import os
import sys
from pathlib import Path

from minidump.minidumpfile import MinidumpFile

from lowmem_runtime import configure_lowmem_symbols, save_results

ROOT = Path(__file__).resolve().parent
DEFAULT_DUMP = ROOT / 'dumps' / 'case3.dmp'
DEFAULT_BASES = [1885639781552]

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

    # Lưu metadata ra file JSON vào thẳng thư mục 'result' cho gọn gàng
    base_name = os.path.splitext(os.path.basename(file_path))[0]
    output_dir = ROOT / "result"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_file = output_dir / f"{base_name}_evidence_metadata.json"
    
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=4)
        
    print(f"    -> MD5: {metadata['md5_hash']}")
    print(f"    -> SHA256: {metadata['sha256_hash']}")
    print(f"    -> Metadata đã được lưu tại: {output_file}")
    print('### Kết thúc module bảo toàn chứng cứ\n')


def parse_args():
    p = argparse.ArgumentParser(description='Low-memory extractor for case3 (có bảo toàn chứng cứ).')
    p.add_argument('--dump', default=str(DEFAULT_DUMP), help='Path to dump file')
    p.add_argument('--bases', nargs='*', type=lambda x: int(x, 0), default=DEFAULT_BASES)
    return p.parse_args()


def main():
    args = parse_args()

    # 1. THỰC HIỆN CẢI TIẾN: Gọi hàm bảo toàn chứng cứ trước khi phân tích dump
    preserve_evidence(args.dump)

    # 2. Bắt đầu luồng phân tích nguyên bản
    print('### start to load symbols at', datetime.datetime.now())
    sys.stdout.flush()
    configure_lowmem_symbols(ROOT)
    from chracer.chromium import Browser, Tab, NavigationEntry
    print('### end to load symbols at', datetime.datetime.now())

    print('### start to extract information at', datetime.datetime.now())
    mdmp = MinidumpFile.parse(args.dump)
    rows = []

    for base in args.bases:
        print('### processing Browser base 0x{:X}'.format(base))
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
                    frame_entry = nav_entry.frame_tree.frame_entry
                    rows.append((
                        session_id,
                        tab_idx,
                        nav_entry.timestamp.to_datetime(),
                        frame_entry.url,
                        frame_entry.referrer.url,
                    ))
                gc.collect()
        except Exception as e:
            print('[WARN] 0x{:X} processing error ({})'.format(base, e))

    print('### end to extract information at', datetime.datetime.now())
    headers = ['SessionID', 'Tab', 'Time', 'URL', 'Referrer']
    
    # Thay đổi tên prefix file đầu ra để thể hiện đây là bản cải tiến (tuỳ chọn)
    table_output, txt_path, csv_path = save_results(ROOT, 'case3_lowmem_1', headers, rows)
    
    print(table_output)
    print(f'### saved text result to {txt_path}')
    print(f'### saved csv result to {csv_path}')


if __name__ == '__main__':
    main()
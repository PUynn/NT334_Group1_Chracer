#!/usr/bin/env python3
import argparse
import datetime
import sys
import os
import hashlib
import json
import gc
from pathlib import Path

import tqdm
from minidump.minidumpfile import MinidumpFile
from minidump.streams import MemoryType, MemoryState, AllocationProtect

from lowmem_runtime import configure_lowmem_symbols, save_results

ROOT = Path(__file__).resolve().parent
DEFAULT_DUMP = ROOT / 'dumps' / 'case_google_chrome.dmp'


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

    # Đảm bảo thư mục result tồn tại và lưu metadata
    output_dir = ROOT / "result"
    output_dir.mkdir(parents=True, exist_ok=True)
    base_name = os.path.splitext(os.path.basename(file_path))[0]
    output_file = output_dir / f"{base_name}_evidence_metadata.json"
    
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=4)
        
    print(f"    -> MD5: {metadata['md5_hash']}")
    print(f"    -> SHA256: {metadata['sha256_hash']}")
    print(f"    -> Metadata đã được lưu tại: {output_file}")
    print('### Kết thúc module bảo toàn chứng cứ\n')


def parse_args():
    p = argparse.ArgumentParser(description='Low-memory extractor for case_google_chrome (có bảo toàn chứng cứ).')
    p.add_argument('--dump', default=str(DEFAULT_DUMP), help='Path to dump file')
    p.add_argument('--bases', nargs='*', type=lambda x: int(x, 0), default=[])
    return p.parse_args()


def main():
    args = parse_args()

    # 1. THỰC HIỆN CẢI TIẾN: Bảo toàn chứng cứ
    preserve_evidence(args.dump)

    # 2. Phân tích nguyên bản
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
            if m.Type == MemoryType.MEM_PRIVATE \
            and m.State == MemoryState.MEM_COMMIT \
            and m.Protect == AllocationProtect.PAGE_READWRITE:
                for addr in range(m.BaseAddress, m.BaseAddress + m.RegionSize - ChromeBrowser.instance_size(), 8):
                    b = ChromeBrowser(mdmp, addr)
                    if not b.validate():
                        continue
                    tabs = b.tab_strip_model.contents_data.entries
                    if len(tabs) < 1:
                        continue
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
                        rows.append((b.session_id, ti, e.timestamp.to_datetime(), e.title.string, fe.url.spec.string))
                    except Exception:
                        continue
        except Exception:
            continue
        finally:
            # Giải phóng bộ nhớ sau mỗi vòng lặp browser để tránh tràn RAM
            gc.collect()

    print('### end to extract information at', datetime.datetime.now())
    headers = ['SessionID', 'Tab', 'Time', 'Title', 'URL']
    
    # Lưu kết quả với tiền tố _1 để phân biệt
    table_output, txt_path, csv_path = save_results(ROOT, 'case_google_chrome_lowmem_1', headers, rows)
    
    print(table_output)
    print(f'### saved text result to {txt_path}')
    print(f'### saved csv result to {csv_path}')


if __name__ == '__main__':
    main()
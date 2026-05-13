#!/usr/bin/env python3
import os
import hashlib
import json
import datetime
from pathlib import Path

# Tìm thư mục gốc của project (thư mục Chracer)
ROOT = Path(__file__).resolve().parent

def preserve_evidence(file_path):
    """
    MODULE CẢI TIẾN 1: Bảo toàn chứng cứ
    Được gọi như một thư viện độc lập bởi các script phân tích.
    """
    print('### [CẢI TIẾN] Bắt đầu module bảo toàn chứng cứ tại', datetime.datetime.now())
    
    if not os.path.exists(file_path):
        print(f"Lỗi: Không tìm thấy file {file_path}")
        exit(1)

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

    # Lưu metadata ra file JSON vào thư mục 'result'
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
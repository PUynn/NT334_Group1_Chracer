#!/usr/bin/env python3
import os
import hashlib
import json
import datetime
from pathlib import Path

# Chracer/acquisition/
ROOT = Path(__file__).resolve().parent


def preserve_evidence(file_path):
    """
    Chain of custody / evidence hashing: compute MD5 and SHA256, write metadata JSON.

    Callable as a library from analysis scripts (`preserve_evidence(path)`).
    """
    print("### Chain-of-custody: started at", datetime.datetime.now())

    if not os.path.exists(file_path):
        print(f"Error: file not found: {file_path}")
        raise SystemExit(1)

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
    
    print("    -> Hashing file (chunk size: 4MB)...")
    with open(file_path, "rb") as f:
        while chunk := f.read(chunk_size):
            md5_hash.update(chunk)
            sha256_hash.update(chunk)
            
    metadata["md5_hash"] = md5_hash.hexdigest()
    metadata["sha256_hash"] = sha256_hash.hexdigest()

    # Write metadata JSON under Chracer/acquisition/result/
    output_dir = ROOT / "result"
    output_dir.mkdir(parents=True, exist_ok=True)
    base_name = os.path.splitext(os.path.basename(file_path))[0]
    output_file = output_dir / f"{base_name}_evidence_metadata.json"
    
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=4)
        
    print(f"    -> MD5: {metadata['md5_hash']}")
    print(f"    -> SHA256: {metadata['sha256_hash']}")
    print(f"    -> Metadata saved to: {output_file}")
    print('### Chain-of-custody module finished.\n')


def main_cli():
    import argparse

    parser = argparse.ArgumentParser(
        description="Compute MD5/SHA256 for a memory dump and write evidence_metadata.json.",
    )
    parser.add_argument("dump_path", help="Path to the memory dump file (.dmp)")
    args = parser.parse_args()
    preserve_evidence(args.dump_path)


if __name__ == "__main__":
    main_cli()
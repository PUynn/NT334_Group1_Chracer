#!/usr/bin/env python3
import argparse
import csv
import json
import re
import time
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

ASCII_URL_RE = re.compile(
    rb"(?i)\b(?:https?|chrome)://[A-Za-z0-9\-._~:/?#\[\]@!$&*+,;=%()]+"
)

UTF16_URL_RE = re.compile(
    rb"(?i)(?:h\x00t\x00t\x00p\x00(?:s\x00)?|c\x00h\x00r\x00o\x00m\x00e\x00)"
    rb":\x00/\x00/\x00(?:[A-Za-z0-9\-._~:/?#\[\]@!$&*+,;=%()]\x00)+"
)

def clean_url(url: str) -> str:
    url = url.strip()
    url = url.replace("\x00", "")
    url = url.strip("\"'<>[]{}")

    # Cắt các ký tự rác thường gặp phía sau URL trong memory dump
    while url and url[-1] in [",", ";", "\"", "'", "<", ">", "\r", "\n", "\t"]:
        url = url[:-1]

    return url

def normalize_url(url: str) -> str:
    url = clean_url(url)

    try:
        p = urlsplit(url)
    except Exception:
        return url

    scheme = p.scheme.lower()
    netloc = p.netloc.lower()

    path = p.path

    # Chuẩn hóa dấu / cuối URL để khớp với ground truth
    if path == "/":
        path = ""
    elif len(path) > 1 and path.endswith("/"):
        path = path.rstrip("/")

    # Bỏ fragment vì thường không quan trọng trong ground truth
    fragment = ""

    return urlunsplit((scheme, netloc, path, p.query, fragment))

def is_valid_candidate(url: str, include_internal: bool) -> bool:
    if not url:
        return False

    if url.startswith("chrome://"):
        return include_internal

    if not (url.startswith("http://") or url.startswith("https://")):
        return False

    # Lọc các chuỗi quá ngắn hoặc quá dài bất thường
    if len(url) < 10 or len(url) > 500:
        return False

    return True

def scan_dump(dump_path: Path, case_id: str, include_internal: bool, chunk_size: int = 16 * 1024 * 1024):
    results = {}
    overlap = 1024
    offset_base = 0
    tail = b""

    with dump_path.open("rb") as f:
        while True:
            chunk = f.read(chunk_size)
            if not chunk:
                break

            data = tail + chunk
            data_offset = offset_base - len(tail)

            # ASCII URL
            for m in ASCII_URL_RE.finditer(data):
                raw = m.group().decode("ascii", errors="ignore")
                raw = clean_url(raw)
                norm = normalize_url(raw)

                if not is_valid_candidate(norm, include_internal):
                    continue

                if norm not in results:
                    results[norm] = {
                        "case_id": case_id,
                        "tool": "regex_baseline",
                        "artifact_type": "url",
                        "encoding": "ascii",
                        "offset": data_offset + m.start(),
                        "url_raw": raw,
                        "url_norm": norm,
                        "window_index": "",
                        "tab_index": "",
                        "nav_order": "",
                        "note": "regex_match_no_context"
                    }

            # UTF-16LE URL
            for m in UTF16_URL_RE.finditer(data):
                raw_bytes = m.group()
                raw = raw_bytes.decode("utf-16le", errors="ignore")
                raw = clean_url(raw)
                norm = normalize_url(raw)

                if not is_valid_candidate(norm, include_internal):
                    continue

                if norm not in results:
                    results[norm] = {
                        "case_id": case_id,
                        "tool": "regex_baseline",
                        "artifact_type": "url",
                        "encoding": "utf-16le",
                        "offset": data_offset + m.start(),
                        "url_raw": raw,
                        "url_norm": norm,
                        "window_index": "",
                        "tab_index": "",
                        "nav_order": "",
                        "note": "regex_match_no_context"
                    }

            tail = data[-overlap:]
            offset_base += len(chunk)

    return list(results.values())

def write_csv(rows, out_path: Path):
    fieldnames = [
        "case_id",
        "tool",
        "artifact_type",
        "encoding",
        "offset",
        "url_raw",
        "url_norm",
        "window_index",
        "tab_index",
        "nav_order",
        "note"
    ]

    with out_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

def main():
    parser = argparse.ArgumentParser(description="Regex/string-search baseline for Chracer memory dump")
    parser.add_argument("--case-id", required=True, help="case1, case2, case3...")
    parser.add_argument("--dump", required=True, help="Path to .dmp file")
    parser.add_argument("--out", required=True, help="Output CSV path")
    parser.add_argument("--runtime", required=True, help="Runtime JSON path")
    parser.add_argument(
        "--include-internal",
        action="store_true",
        help="Also keep chrome:// URLs. Default only keeps http/https URLs."
    )

    args = parser.parse_args()

    dump_path = Path(args.dump)
    out_path = Path(args.out)
    runtime_path = Path(args.runtime)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    runtime_path.parent.mkdir(parents=True, exist_ok=True)

    start = time.time()
    rows = scan_dump(
        dump_path=dump_path,
        case_id=args.case_id,
        include_internal=args.include_internal
    )
    end = time.time()

    write_csv(rows, out_path)

    runtime = {
        "case_id": args.case_id,
        "tool": "regex_baseline",
        "dump": str(dump_path),
        "output_csv": str(out_path),
        "total_recovered": len(rows),
        "start_time_epoch": start,
        "end_time_epoch": end,
        "runtime_seconds": round(end - start, 4)
    }

    with runtime_path.open("w", encoding="utf-8") as f:
        json.dump(runtime, f, indent=2, ensure_ascii=False)

    print(f"[OK] Case: {args.case_id}")
    print(f"[OK] Dump: {dump_path}")
    print(f"[OK] Output: {out_path}")
    print(f"[OK] Runtime: {runtime_path}")
    print(f"[OK] Total recovered URLs: {len(rows)}")
    print(f"[OK] Runtime seconds: {round(end - start, 4)}")

if __name__ == "__main__":
    main()
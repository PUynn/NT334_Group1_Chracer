#!/usr/bin/env python3
import csv
import re
from pathlib import Path
from datetime import datetime

summary_files = {
    "case1": "evaluation/summary/case1_chracer_summary.csv",
    "case2": "evaluation/summary/case2_chracer_summary.csv",
    "case3": "evaluation/summary/case3_chracer_summary.csv",
}

log_files = {
    "case1": "result/case1_lowmem_20260515_181021.txt",
    "case2": "result/case2_lowmem_20260515_181752.txt",
    "case3": "result/case3_lowmem_20260515_182521.txt",
}

dt_pattern = re.compile(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}(?:\.\d+)?")

def parse_tta_seconds(log_path):
    text = Path(log_path).read_text(encoding="utf-8", errors="ignore")
    matches = dt_pattern.findall(text)

    if len(matches) < 2:
        return ""

    times = []
    for m in matches:
        try:
            times.append(datetime.fromisoformat(m))
        except ValueError:
            pass

    if len(times) < 2:
        return ""

    return round((max(times) - min(times)).total_seconds(), 4)

def update_summary(summary_path, tta):
    path = Path(summary_path)

    with path.open("r", newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
        fieldnames = f.readline()

    # Đọc lại đúng cách
    with path.open("r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        fields = reader.fieldnames

    if "tta_seconds" not in fields:
        fields.append("tta_seconds")

    for row in rows:
        row["tta_seconds"] = tta

    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)

for case_id in ["case1", "case2", "case3"]:
    log_path = Path(log_files[case_id])
    summary_path = Path(summary_files[case_id])

    if not log_path.exists():
        print(f"[WARN] Missing log: {log_path}")
        continue

    if not summary_path.exists():
        print(f"[WARN] Missing summary: {summary_path}")
        continue

    tta = parse_tta_seconds(log_path)
    update_summary(summary_path, tta)
    print(f"[OK] {case_id}: TTA = {tta} seconds")

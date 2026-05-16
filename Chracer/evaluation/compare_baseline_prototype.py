#!/usr/bin/env python3
import csv
from pathlib import Path

summary_dir = Path("evaluation/summary")
out_path = Path("evaluation/final_compare.csv")

files = [
    summary_dir / "case1_regex_summary.csv",
    summary_dir / "case1_chracer_summary.csv",
    summary_dir / "case2_regex_summary.csv",
    summary_dir / "case2_chracer_summary.csv",
    summary_dir / "case3_regex_summary.csv",
    summary_dir / "case3_chracer_summary.csv",
]

rows = []

for file in files:
    if not file.exists():
        print(f"[WARN] Missing: {file}")
        continue

    with file.open("r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(row)

if not rows:
    raise SystemExit("[ERROR] No summary files found")

# Gom tất cả field, vì regex_summary và chracer_summary có thể hơi khác cột
fieldnames = []
for row in rows:
    for key in row.keys():
        if key not in fieldnames:
            fieldnames.append(key)

with out_path.open("w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(rows)

print(f"[OK] Final comparison exported: {out_path}")

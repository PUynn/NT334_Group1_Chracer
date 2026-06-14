#!/usr/bin/env python3
"""
Pipeline: hash metadata → run Chracer (lowmem case) → evaluate_chracer → consolidated report.

1. preserve_evidence (hash_dump)
2. subprocess case{N}_lowmem.py (writes Chracer/result/case*_lowmem_*.csv)
3. Normalize report CSV for ground-truth evaluation → evaluate_chracer.py
4. generate_all_reports for evaluation summary table
"""
from __future__ import annotations

import argparse
import csv
import importlib.util
import subprocess
import sys
import time
from collections import defaultdict
from pathlib import Path
from typing import Any

CHRACER_ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = CHRACER_ROOT.parent

for _p in (CHRACER_ROOT, PROJECT_ROOT):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

EXTRACTION_REPORTS_DIR = CHRACER_ROOT / "result"
EVAL_ROOT = CHRACER_ROOT / "evaluation"
EVAL_SCRIPT = EVAL_ROOT / "evaluate.py"
GROUND_TRUTH_DIR = CHRACER_ROOT / "ground_truth"
RESULTS_DIR = EVAL_ROOT / "results"

from acquisition.hash_dump import preserve_evidence  # noqa: E402
from reporting.generate_report import generate_all_reports  # noqa: E402


def _load_normalize_url():
    spec = importlib.util.spec_from_file_location("evaluate_mod", EVAL_SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.normalize_url


normalize_url = None  # lazy


def _norm_color(name: str) -> str:
    s = (name or "").strip().lower()
    if len(s) > 1 and s[0] == "k":
        return s[1:]
    return s


CASE_CONFIG = {
    "case1": {
        "script": "case1_lowmem.py",
        "dump_default": CHRACER_ROOT / "dumps" / "case1.dmp",
        "artifact": "url",
        "gt": GROUND_TRUTH_DIR / "case1_windows_urls.csv",
        "report_glob": "case1_lowmem_*.csv",
    },
    "case2": {
        "script": "case2_lowmem.py",
        "dump_default": CHRACER_ROOT / "dumps" / "case2.dmp",
        "artifact": "tab_group",
        "gt": GROUND_TRUTH_DIR / "case2_tab_groups.csv",
        "report_glob": "case2_lowmem_*.csv",
    },
    "case3": {
        "script": "case3_lowmem.py",
        "dump_default": CHRACER_ROOT / "dumps" / "case3.dmp",
        "artifact": "url",
        "gt": GROUND_TRUTH_DIR / "case3_navigation_urls.csv",
        "report_glob": "case3_lowmem_*.csv",
    },
}


def find_latest_report(glob_pattern: str, reports_dir: Path) -> Path | None:
    if not reports_dir.is_dir():
        return None
    files = list(reports_dir.glob(glob_pattern))
    if not files:
        return None
    return max(files, key=lambda p: p.stat().st_mtime)


def report_rows_to_eval_csv(case_id: str, report_path: Path, out_path: Path) -> None:
    global normalize_url
    if normalize_url is None:
        normalize_url = _load_normalize_url()

    with report_path.open("r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    if not reader.fieldnames:
        raise SystemExit(f"[ERROR] Empty CSV or missing header row: {report_path}")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_fields: list[str]

    if case_id in ("case1", "case3"):
        out_fields = [
            "case_id",
            "artifact_type",
            "window_index",
            "tab_index",
            "nav_order",
            "url_raw",
            "url_norm",
            "referrer_norm",
            "referrer_raw",
        ]
        session_order: list[str] = []
        seen = set()
        for r in rows:
            sid = (r.get("SessionID") or "").strip()
            if sid and sid not in seen:
                seen.add(sid)
                session_order.append(sid)
        win_map = {sid: str(i + 1) for i, sid in enumerate(session_order)}

        key_seq: dict[tuple[str, str], int] = defaultdict(int)
        eval_rows: list[dict[str, str]] = []

        for r in rows:
            url = (r.get("URL") or "").strip()
            if not url or url == "N/A":
                continue
            sid = (r.get("SessionID") or "").strip()
            tab_raw = r.get("Tab", "0")
            try:
                tab_i = int(str(tab_raw).strip())
            except ValueError:
                tab_i = 0
            tab_index = str(tab_i + 1)
            win = win_map.get(sid, "1")

            k = (sid, str(tab_i))
            key_seq[k] += 1
            nav_order = str(key_seq[k])

            eval_rows.append({
                "case_id": case_id,
                "artifact_type": "url",
                "window_index": win,
                "tab_index": tab_index,
                "nav_order": nav_order,
                "url_raw": url,
                "url_norm": normalize_url(url),
                "referrer_norm": "",
                "referrer_raw": "",
            })

    elif case_id == "case2":
        out_fields = [
            "case_id",
            "artifact_type",
            "group_name",
            "group_color",
            "tab_indexes",
            "tab_count",
        ]
        groups: dict[tuple[str, str], list[int]] = defaultdict(list)
        for r in rows:
            gname = (r.get("TabGroup") or "").strip()
            if not gname:
                continue
            raw_col = r.get("TabGroupColor") or ""
            gcolor = _norm_color(raw_col)
            try:
                tab_i = int(str(r.get("Tab", "0")).strip())
            except ValueError:
                tab_i = 0
            groups[(gname, gcolor)].append(tab_i)

        eval_rows = []
        for (gname, gcolor), tabs in sorted(groups.items(), key=lambda x: x[0][0]):
            one_based = sorted({t + 1 for t in tabs})
            eval_rows.append({
                "case_id": case_id,
                "artifact_type": "tab_group",
                "group_name": gname,
                "group_color": gcolor,
                "tab_indexes": ",".join(str(x) for x in one_based),
                "tab_count": str(len(one_based)),
            })
    else:
        raise SystemExit(f"[ERROR] Unsupported case_id: {case_id}")

    with out_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=out_fields)
        w.writeheader()
        for row in eval_rows:
            w.writerow({k: row.get(k, "") for k in out_fields})

    print(f"[OK] Wrote Chracer eval input: {out_path} ({len(eval_rows)} rows)")


def run_case_script(script_name: str, dump: Path, bases: list[int] | None) -> float:
    script = CHRACER_ROOT / script_name
    if not script.is_file():
        raise SystemExit(f"[ERROR] Script not found: {script}")

    cmd = [sys.executable, str(script), "--dump", str(dump)]
    if bases:
        cmd.append("--bases")
        cmd.extend(str(b) for b in bases)

    t0 = time.perf_counter()
    subprocess.run(cmd, check=True, cwd=str(CHRACER_ROOT))
    return round(time.perf_counter() - t0, 4)


def run_evaluation(
    case_id: str,
    artifact: str,
    gt: Path,
    result_csv: Path,
    tta: str,
) -> tuple[Path, Path]:
    detail = EVAL_ROOT / "details" / f"{case_id}_chracer_detail.csv"
    summary = EVAL_ROOT / "summary" / f"{case_id}_chracer_summary.csv"
    cmd = [
        sys.executable,
        str(EVAL_SCRIPT),
        "chracer",
        "--case",
        case_id,
        "--gt",
        str(gt),
        "--result",
        str(result_csv),
        "--artifact-type",
        artifact,
        "--out-detail",
        str(detail),
        "--out-summary",
        str(summary),
        "--tta-seconds",
        tta,
    ]
    subprocess.run(cmd, check=True)
    return detail, summary


def pipeline_one_case(
    case_id: str,
    dump: Path,
    bases: list[int] | None,
    skip_hash: bool,
    extraction_reports_dir: Path,
) -> dict[str, Any]:
    cfg = CASE_CONFIG.get(case_id)
    if not cfg:
        raise SystemExit(f"[ERROR] Invalid case: {case_id}. Choose one of: {', '.join(CASE_CONFIG)}")

    if not skip_hash:
        print(f"### [1/4] Hash metadata: {dump}")
        preserve_evidence(str(dump))
    else:
        print("### [1/4] Skipping hash (--skip-hash)")

    print(f"### [2/4] Running {cfg['script']} …")
    tta_sec = run_case_script(cfg["script"], dump, bases)

    report = find_latest_report(cfg["report_glob"], extraction_reports_dir)
    if not report:
        raise SystemExit(
            f"[ERROR] No report matching {cfg['report_glob']} under {extraction_reports_dir}"
        )

    result_csv = RESULTS_DIR / f"{case_id}_chracer_for_eval.csv"
    print(f"### [3/4] Normalizing extractor output → {result_csv.name}")
    report_rows_to_eval_csv(case_id, report, result_csv)

    print("### [4/4] evaluate.py chracer")
    detail, summary = run_evaluation(
        case_id,
        cfg["artifact"],
        cfg["gt"],
        result_csv,
        str(tta_sec),
    )
    print(f"  detail:  {detail}")
    print(f"  summary: {summary}")

    meta = CHRACER_ROOT / "acquisition" / "result" / f"{dump.stem}_evidence_metadata.json"
    return {
        "case_id": case_id,
        "summary_path": summary,
        "metadata_path": meta,
        "tta_seconds": tta_sec,
    }


def merge_summaries(summaries: list[Path], out_csv: Path) -> tuple[list[str], list[list[str]]]:
    rows: list[dict[str, str]] = []
    fieldnames: list[str] = []
    for p in summaries:
        if not p.is_file():
            continue
        with p.open("r", newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                for k in row:
                    if k not in fieldnames:
                        fieldnames.append(k)
                rows.append(dict(row))

    out_csv.parent.mkdir(parents=True, exist_ok=True)
    with out_csv.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)

    headers = fieldnames
    data = [[row.get(h, "") for h in headers] for row in rows]
    return headers, data


def export_final_report(
    case_name: str,
    headers: list[str],
    data: list[list[str]],
    metadata_path: Path,
    output_dir: Path,
) -> tuple[str, str, str]:
    output_dir.mkdir(parents=True, exist_ok=True)
    return generate_all_reports(
        case_name=case_name,
        headers=headers,
        data=data,
        metadata_file_path=str(metadata_path) if metadata_path.is_file() else str(metadata_path),
        output_dir=str(output_dir),
    )


def parse_args():
    p = argparse.ArgumentParser(description="Chracer pipeline: hash → extract → evaluate → report")
    p.add_argument(
        "--case",
        choices=list(CASE_CONFIG.keys()) + ["all"],
        default="case1",
        help="Case to run, or 'all' for case1, case2, and case3",
    )
    p.add_argument("--dump", default="", help="Path to .dmp file (default: per-case path in CASE_CONFIG)")
    p.add_argument(
        "--bases",
        nargs="*",
        type=lambda x: int(x, 0),
        default=None,
        help="Browser base address(es), hex or decimal (default: from the case script)",
    )
    p.add_argument(
        "--skip-hash",
        action="store_true",
        help="Do not call preserve_evidence in main (case scripts may still hash)",
    )
    p.add_argument(
        "--extraction-reports-dir",
        default=str(EXTRACTION_REPORTS_DIR),
        help="Directory with extractor CSVs (default: Chracer/result/, glob caseN_lowmem_*.csv)",
    )
    p.add_argument(
        "--pipeline-output-dir",
        default=str(PROJECT_ROOT / "reports"),
        help="Output directory for pipeline summary CSV/JSON/HTML",
    )
    return p.parse_args()


def main():
    args = parse_args()
    extraction_reports_dir = Path(args.extraction_reports_dir)
    pipeline_output_dir = Path(args.pipeline_output_dir)

    cases = list(CASE_CONFIG.keys()) if args.case == "all" else [args.case]
    done: list[dict[str, Any]] = []

    for cid in cases:
        cfg = CASE_CONFIG[cid]
        dump = Path(args.dump) if args.dump else Path(cfg["dump_default"])
        if not dump.is_file():
            print(f"[WARN] Skipping {cid}: dump not found: {dump}")
            continue
        info = pipeline_one_case(cid, dump, args.bases, args.skip_hash, extraction_reports_dir)
        done.append(info)

    if not done:
        raise SystemExit("[ERROR] No cases completed successfully.")

    summaries = [Path(x["summary_path"]) for x in done]
    meta_ref = Path(done[-1]["metadata_path"])
    merged_csv = EVAL_ROOT / "pipeline_chracer_summary.csv"
    headers, data = merge_summaries(summaries, merged_csv)
    print(f"[OK] Merged summaries: {merged_csv}")

    csv_p, json_p, html_p = export_final_report(
        case_name="chracer_pipeline_eval",
        headers=headers,
        data=data,
        metadata_path=meta_ref,
        output_dir=pipeline_output_dir,
    )
    print("### Chracer pipeline evaluation report:")
    print(f"  CSV:  {csv_p}")
    print(f"  JSON: {json_p}")
    print(f"  HTML: {html_p}")


if __name__ == "__main__":
    main()

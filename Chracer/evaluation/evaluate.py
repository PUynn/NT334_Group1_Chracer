#!/usr/bin/env python3
"""
evaluate.py — Unified evaluation script for Chracer project.

Consolidates: evaluate_chracer.py, evaluate_regex.py,
              fill_chracer_tta.py, compare_baseline_prototype.py

Sub-commands:
    chracer   Evaluate Chracer results against ground truth
    regex     Evaluate Regex baseline results against ground truth
    compare   Merge all summary CSVs into final_compare.csv
    all       Auto-discover and evaluate all cases + compare

Usage:
    python3 evaluation/evaluate.py chracer --case case1 --gt GT.csv --result RESULT.csv
    python3 evaluation/evaluate.py regex   --case case1 --gt GT.csv --result RESULT.csv
    python3 evaluation/evaluate.py compare
    python3 evaluation/evaluate.py all
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit, urlunsplit

# ── Path constants ───────────────────────────────────────────────────────────

SCRIPT_DIR = Path(__file__).resolve().parent          # evaluation/
CHRACER_ROOT = SCRIPT_DIR.parent                      # Chracer/
GROUND_TRUTH_DIR = CHRACER_ROOT / "ground_truth"
BASELINE_RESULTS_DIR = CHRACER_ROOT / "baseline" / "results"
EVAL_RESULTS_DIR = SCRIPT_DIR / "results"
DETAIL_DIR = SCRIPT_DIR / "details"
SUMMARY_DIR = SCRIPT_DIR / "summary"


# ═════════════════════════════════════════════════════════════════════════════
# Core Utilities
# ═════════════════════════════════════════════════════════════════════════════

def normalize_url(url: str) -> str:
    """Normalize URL for comparison: lowercase scheme/host, strip trailing slash, drop fragment."""
    if url is None:
        return ""

    url = str(url).strip().replace("\x00", "")
    url = url.strip("\"'<>[]{}()")

    if not url:
        return ""

    try:
        p = urlsplit(url)
    except Exception:
        return url

    scheme = p.scheme.lower()
    netloc = p.netloc.lower()
    path = p.path

    if path == "/":
        path = ""
    elif len(path) > 1 and path.endswith("/"):
        path = path.rstrip("/")

    return urlunsplit((scheme, netloc, path, p.query, ""))


# Known URL equivalences (e.g. redirects)
_URL_EQUIV = {
    "https://www.chromium.org": {
        "https://www.chromium.org",
        "https://www.chromium.org/chromium-projects",
    },
    "https://www.chromium.org/chromium-projects": {
        "https://www.chromium.org",
        "https://www.chromium.org/chromium-projects",
    },
}


def is_equiv_url(a: str, b: str) -> bool:
    """Check if two URLs are equivalent (exact match or known redirect)."""
    a = normalize_url(a)
    b = normalize_url(b)
    if a == b:
        return True
    if a in _URL_EQUIV and b in _URL_EQUIV[a]:
        return True
    return False


def read_csv(path: Path) -> list[dict[str, str]]:
    """Read a CSV file and return a list of dicts."""
    with path.open("r", newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def write_csv(path: Path, rows: list[dict[str, str]], fieldnames: list[str]) -> None:
    """Write a list of dicts as CSV."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def get_url(row: dict[str, str]) -> str:
    """Extract normalized URL from a row (tries multiple column names)."""
    for col in ("url_norm", "url_raw", "url"):
        if col in row and row[col]:
            return normalize_url(row[col])
    return ""


def get_from_url(row: dict[str, str]) -> str:
    """Extract normalized referrer/from-URL from a row."""
    for col in ("from_url_norm", "from_url_raw", "referrer_norm", "referrer_raw", "from_raw"):
        if col in row and row[col]:
            return normalize_url(row[col])
    return ""


def split_context(row: dict[str, str]) -> list[str]:
    """Parse expected_context field into a list of context field names."""
    ctx = row.get("expected_context", "")
    if not ctx:
        return ["url"]
    return [x.strip() for x in ctx.split("+") if x.strip()]


def same_value(a: Any, b: Any) -> bool:
    return str(a).strip().lower() == str(b).strip().lower()


def parse_tabs(value: Any) -> set[str]:
    if value is None:
        return set()
    value = str(value).strip().strip('"').strip("'")
    if not value:
        return set()
    return {x.strip() for x in value.split(",") if x.strip()}


# ═════════════════════════════════════════════════════════════════════════════
# Chracer Evaluator
# ═════════════════════════════════════════════════════════════════════════════

def compute_url_completeness(gt: dict, result: dict) -> tuple[float, str]:
    """Compute completeness score for a URL artifact match."""
    fields = split_context(gt)
    matched = []

    for field in fields:
        if field == "url":
            if is_equiv_url(get_url(gt), get_url(result)):
                matched.append(field)
        elif field in ("window", "window_index"):
            if same_value(gt.get("window_index", ""), result.get("window_index", "")):
                matched.append(field)
        elif field in ("tab", "tab_index"):
            if same_value(gt.get("tab_index", ""), result.get("tab_index", "")):
                matched.append(field)
        elif field in ("order", "nav_order"):
            if same_value(gt.get("nav_order", ""), result.get("nav_order", "")):
                matched.append(field)
        elif field in ("from", "referrer"):
            gt_from = get_from_url(gt)
            rs_from = get_from_url(result)
            if gt_from and rs_from and is_equiv_url(gt_from, rs_from):
                matched.append(field)

    completeness = len(matched) / len(fields) if fields else 0
    return completeness, "+".join(matched)


def compute_group_completeness(gt: dict, result: dict) -> tuple[float, str]:
    """Compute completeness score for a tab_group artifact match."""
    fields = split_context(gt)
    matched = []

    for field in fields:
        if field == "group_name":
            if same_value(gt.get("group_name", ""), result.get("group_name", "")):
                matched.append(field)
        elif field == "group_color":
            if same_value(gt.get("group_color", ""), result.get("group_color", "")):
                matched.append(field)
        elif field == "tab_indexes":
            if parse_tabs(gt.get("tab_indexes", "")) == parse_tabs(result.get("tab_indexes", "")):
                matched.append(field)
        elif field == "tab_count":
            if same_value(gt.get("tab_count", ""), result.get("tab_count", "")):
                matched.append(field)

    completeness = len(matched) / len(fields) if fields else 0
    return completeness, "+".join(matched)


def _evaluate_urls(case_id: str, gt_rows: list[dict], result_rows: list[dict]) -> tuple[
    list[dict], int, int, int, int, int, list[float]
]:
    """Evaluate URL artifacts: TP/FP/FN + completeness scores."""
    details: list[dict] = []
    used_result_indexes: set[int] = set()

    tp = fn = 0
    gt_url_rows = [r for r in gt_rows if r.get("artifact_type", "").lower() == "url"]
    result_url_rows = [r for r in result_rows if r.get("artifact_type", "").lower() == "url"]
    completeness_scores: list[float] = []

    for gt in gt_url_rows:
        gt_url = get_url(gt)
        matched_idx = None

        for idx, rs in enumerate(result_url_rows):
            if idx in used_result_indexes:
                continue
            if is_equiv_url(gt_url, get_url(rs)):
                matched_idx = idx
                break

        if matched_idx is not None:
            rs = result_url_rows[matched_idx]
            used_result_indexes.add(matched_idx)
            tp += 1

            completeness, matched_context = compute_url_completeness(gt, rs)
            completeness_scores.append(completeness)

            details.append({
                "case_id": case_id,
                "artifact_id": gt.get("artifact_id", ""),
                "artifact_type": "url",
                "status": "TP",
                "expected": gt_url,
                "recovered": get_url(rs),
                "expected_context": gt.get("expected_context", ""),
                "matched_context": matched_context,
                "completeness": round(completeness, 4),
                "note": "URL recovered by Chracer",
            })
        else:
            fn += 1
            completeness_scores.append(0)
            details.append({
                "case_id": case_id,
                "artifact_id": gt.get("artifact_id", ""),
                "artifact_type": "url",
                "status": "FN",
                "expected": gt_url,
                "recovered": "",
                "expected_context": gt.get("expected_context", ""),
                "matched_context": "",
                "completeness": 0,
                "note": "Ground truth URL not recovered by Chracer",
            })

    # Filter out ignorable internal URLs from FP count
    ignorable_prefixes = ("chrome://", "edge://", "about:")
    
    fp = 0
    for idx, rs in enumerate(result_url_rows):
        if idx not in used_result_indexes:
            recovered_url = get_url(rs)
            if recovered_url.startswith(ignorable_prefixes):
                # Skip internal noise
                continue
                
            fp += 1
            details.append({
                "case_id": case_id,
                "artifact_id": "",
                "artifact_type": "url",
                "status": "FP",
                "expected": "",
                "recovered": recovered_url,
                "expected_context": "",
                "matched_context": "",
                "completeness": 0,
                "note": "Chracer recovered URL not present in ground truth",
            })

    gt_total = len(gt_url_rows)
    recovered_total = len(result_url_rows)
    return details, gt_total, recovered_total, tp, fp, fn, completeness_scores


def _evaluate_tab_groups(case_id: str, gt_rows: list[dict], result_rows: list[dict]) -> tuple[
    list[dict], int, int, int, int, int, list[float]
]:
    """Evaluate tab_group artifacts: TP/FP/FN + completeness scores."""
    details: list[dict] = []
    used_result_indexes: set[int] = set()

    tp = fn = 0
    gt_group_rows = [r for r in gt_rows if r.get("artifact_type", "").lower() == "tab_group"]
    result_group_rows = [r for r in result_rows if r.get("artifact_type", "").lower() == "tab_group"]
    completeness_scores: list[float] = []

    def _group_str(row: dict) -> str:
        return f'{row.get("group_name", "")}:{row.get("group_color", "")}:{row.get("tab_indexes", "")}'

    for gt in gt_group_rows:
        gt_group = gt.get("group_name", "")
        matched_idx = None

        for idx, rs in enumerate(result_group_rows):
            if idx in used_result_indexes:
                continue
            if same_value(gt_group, rs.get("group_name", "")):
                matched_idx = idx
                break

        if matched_idx is not None:
            rs = result_group_rows[matched_idx]
            used_result_indexes.add(matched_idx)
            tp += 1

            completeness, matched_context = compute_group_completeness(gt, rs)
            completeness_scores.append(completeness)

            details.append({
                "case_id": case_id,
                "artifact_id": gt.get("artifact_id", ""),
                "artifact_type": "tab_group",
                "status": "TP",
                "expected": _group_str(gt),
                "recovered": _group_str(rs),
                "expected_context": gt.get("expected_context", ""),
                "matched_context": matched_context,
                "completeness": round(completeness, 4),
                "note": "Tab group recovered by Chracer",
            })
        else:
            fn += 1
            completeness_scores.append(0)
            details.append({
                "case_id": case_id,
                "artifact_id": gt.get("artifact_id", ""),
                "artifact_type": "tab_group",
                "status": "FN",
                "expected": _group_str(gt),
                "recovered": "",
                "expected_context": gt.get("expected_context", ""),
                "matched_context": "",
                "completeness": 0,
                "note": "Ground truth tab group not recovered by Chracer",
            })

    fp = 0
    for idx, rs in enumerate(result_group_rows):
        if idx not in used_result_indexes:
            fp += 1
            details.append({
                "case_id": case_id,
                "artifact_id": "",
                "artifact_type": "tab_group",
                "status": "FP",
                "expected": "",
                "recovered": _group_str(rs),
                "expected_context": "",
                "matched_context": "",
                "completeness": 0,
                "note": "Chracer recovered tab group not present in ground truth",
            })

    gt_total = len(gt_group_rows)
    recovered_total = len(result_group_rows)
    return details, gt_total, recovered_total, tp, fp, fn, completeness_scores


def _auto_detect_artifact_type(gt_rows: list[dict]) -> str:
    """Auto-detect artifact_type from ground truth rows."""
    types = {r.get("artifact_type", "").lower() for r in gt_rows}
    if "tab_group" in types:
        return "tab_group"
    return "url"


def run_chracer_eval(
    case_id: str,
    gt_path: Path,
    result_path: Path,
    artifact_type: str | None = None,
    tta_seconds: str = "",
    out_detail: Path | None = None,
    out_summary: Path | None = None,
) -> dict[str, Any]:
    """Run Chracer evaluation for one case. Returns summary dict."""
    gt_rows = read_csv(gt_path)
    result_rows = read_csv(result_path)

    if artifact_type is None:
        artifact_type = _auto_detect_artifact_type(gt_rows)

    if artifact_type == "url":
        details, gt_total, recovered_total, tp, fp, fn, c_scores = _evaluate_urls(
            case_id, gt_rows, result_rows
        )
    else:
        details, gt_total, recovered_total, tp, fp, fn, c_scores = _evaluate_tab_groups(
            case_id, gt_rows, result_rows
        )

    recovery_rate = tp / gt_total if gt_total else 0
    fpr_noise_rate = fp / recovered_total if recovered_total else 0
    completeness = sum(c_scores) / len(c_scores) if c_scores else 0

    # Write detail CSV
    detail_path = out_detail or (DETAIL_DIR / f"{case_id}_chracer_detail.csv")
    detail_fields = [
        "case_id", "artifact_id", "artifact_type", "status",
        "expected", "recovered", "expected_context", "matched_context",
        "completeness", "note",
    ]
    write_csv(detail_path, details, detail_fields)

    # Build and write summary
    summary = {
        "case_id": case_id,
        "tool": "chracer",
        "artifact_type": artifact_type,
        "ground_truth_total": gt_total,
        "recovered_total": recovered_total,
        "TP": tp,
        "FP": fp,
        "FN": fn,
        "recovery_rate": round(recovery_rate, 4),
        "fpr_noise_rate": round(fpr_noise_rate, 4),
        "completeness": round(completeness, 4),
        "tta_seconds": tta_seconds,
        "note": "Chracer evaluation against ground truth",
    }
    summary_path = out_summary or (SUMMARY_DIR / f"{case_id}_chracer_summary.csv")
    write_csv(summary_path, [summary], list(summary.keys()))

    print(f"[OK] Chracer eval: {case_id} ({artifact_type})")
    print(f"  Detail:  {detail_path}")
    print(f"  Summary: {summary_path}")
    print(f"  TP={tp}  FP={fp}  FN={fn}  Recovery={recovery_rate:.2%}  Completeness={completeness:.2%}")

    return summary


# ═════════════════════════════════════════════════════════════════════════════
# Regex Evaluator
# ═════════════════════════════════════════════════════════════════════════════

def _get_runtime_seconds(runtime_path: str) -> str:
    """Read runtime_seconds from a JSON file."""
    if not runtime_path:
        return ""
    path = Path(runtime_path)
    if not path.exists():
        return ""
    try:
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        return str(data.get("runtime_seconds", ""))
    except Exception:
        return ""


def run_regex_eval(
    case_id: str,
    gt_path: Path,
    result_path: Path,
    runtime_json: str = "",
    out_detail: Path | None = None,
    out_summary: Path | None = None,
) -> dict[str, Any]:
    """Run Regex baseline evaluation for one case. Returns summary dict."""
    gt_rows = read_csv(gt_path)
    result_rows = read_csv(result_path)

    gt_url_rows = [
        r for r in gt_rows
        if r.get("artifact_type", "").lower() == "url" and get_url(r)
    ]

    # Detect if GT has tab_group artifacts (regex can't recover them)
    gt_group_rows = [r for r in gt_rows if r.get("artifact_type", "").lower() == "tab_group"]

    result_urls: dict[str, dict] = {}
    for r in result_rows:
        u = get_url(r)
        if u:
            result_urls.setdefault(u, r)

    gt_urls = {get_url(r): r for r in gt_url_rows}

    detail_rows: list[dict] = []
    tp = fn = fp = 0
    completeness_scores: list[float] = []

    # TP / FN
    for gt_url, gt_row in gt_urls.items():
        if gt_url in result_urls:
            tp += 1
            fields = split_context(gt_row)
            matched_fields = 1 if "url" in fields else 0
            completeness = matched_fields / len(fields) if fields else 0
            completeness_scores.append(completeness)

            detail_rows.append({
                "case_id": case_id,
                "artifact_id": gt_row.get("artifact_id", ""),
                "status": "TP",
                "url_norm": gt_url,
                "expected_context": gt_row.get("expected_context", ""),
                "matched_context": "url",
                "completeness": round(completeness, 4),
                "note": "Regex found URL but has no tab/window/navigation context",
            })
        else:
            fn += 1
            completeness_scores.append(0)
            detail_rows.append({
                "case_id": case_id,
                "artifact_id": gt_row.get("artifact_id", ""),
                "status": "FN",
                "url_norm": gt_url,
                "expected_context": gt_row.get("expected_context", ""),
                "matched_context": "",
                "completeness": 0,
                "note": "Ground truth URL not found by Regex",
            })

    # FP
    ignorable_prefixes = ("chrome://", "edge://", "about:")
    for result_url in result_urls:
        if result_url not in gt_urls:
            if result_url.startswith(ignorable_prefixes):
                continue
                
            fp += 1
            detail_rows.append({
                "case_id": case_id,
                "artifact_id": "",
                "status": "FP",
                "url_norm": result_url,
                "expected_context": "",
                "matched_context": "url",
                "completeness": 0,
                "note": "Regex recovered URL not present in ground truth",
            })

    gt_total = len(gt_urls)
    recovered_total = len(result_urls)

    recovery_rate = tp / gt_total if gt_total else 0
    fpr_noise_rate = fp / recovered_total if recovered_total else 0
    completeness_avg = sum(completeness_scores) / len(completeness_scores) if completeness_scores else 0

    tta = _get_runtime_seconds(runtime_json)

    # If there are tab_group ground-truth rows, add a note that regex can't recover them
    if gt_group_rows and not gt_url_rows:
        summary = {
            "case_id": case_id,
            "tool": "regex_baseline",
            "artifact_type": "tab_group",
            "ground_truth_total": len(gt_group_rows),
            "recovered_total": 0,
            "TP": "N/A",
            "FP": "N/A",
            "FN": "N/A",
            "recovery_rate": "N/A",
            "fpr_noise_rate": "N/A",
            "completeness": "N/A",
            "tta_seconds": tta,
            "note": "Regex baseline does not support tab-group recovery",
        }
    else:
        summary = {
            "case_id": case_id,
            "tool": "regex_baseline",
            "artifact_type": "url",
            "ground_truth_total": gt_total,
            "recovered_total": recovered_total,
            "TP": tp,
            "FP": fp,
            "FN": fn,
            "recovery_rate": round(recovery_rate, 4),
            "fpr_noise_rate": round(fpr_noise_rate, 4),
            "completeness": round(completeness_avg, 4),
            "tta_seconds": tta,
            "note": "Regex baseline only evaluates URL recovery, not tab/window/tab-group context",
        }

    # Write detail CSV
    detail_path = out_detail or (DETAIL_DIR / f"{case_id}_regex_detail.csv")
    detail_fields = [
        "case_id", "artifact_id", "status", "url_norm",
        "expected_context", "matched_context", "completeness", "note",
    ]
    write_csv(detail_path, detail_rows, detail_fields)

    # Write summary CSV
    summary_path = out_summary or (SUMMARY_DIR / f"{case_id}_regex_summary.csv")
    write_csv(summary_path, [summary], list(summary.keys()))

    print(f"[OK] Regex eval: {case_id}")
    print(f"  Detail:  {detail_path}")
    print(f"  Summary: {summary_path}")
    if gt_group_rows and not gt_url_rows:
        print(f"  Note: Regex baseline does not support tab-group recovery")
    else:
        print(f"  TP={tp}  FP={fp}  FN={fn}  Recovery={recovery_rate:.2%}  Noise={fpr_noise_rate:.2%}")

    return summary


# ═════════════════════════════════════════════════════════════════════════════
# TTA (Time-to-Analysis) helper
# ═════════════════════════════════════════════════════════════════════════════

_DT_PATTERN = re.compile(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}(?:\.\d+)?")


def parse_tta_from_log(log_path: Path) -> str:
    """Compute TTA in seconds from timestamps in a log file."""
    if not log_path.exists():
        return ""

    text = log_path.read_text(encoding="utf-8", errors="ignore")
    matches = _DT_PATTERN.findall(text)

    times = []
    for m in matches:
        try:
            times.append(datetime.fromisoformat(m))
        except ValueError:
            pass

    if len(times) < 2:
        return ""

    return str(round((max(times) - min(times)).total_seconds(), 4))


# ═════════════════════════════════════════════════════════════════════════════
# Comparison
# ═════════════════════════════════════════════════════════════════════════════

def run_compare(out_path: Path | None = None) -> Path:
    """Merge all summary CSVs in summary/ into a single comparison CSV."""
    out = out_path or (SCRIPT_DIR / "final_compare.csv")

    rows: list[dict[str, str]] = []
    fieldnames: list[str] = []

    if not SUMMARY_DIR.is_dir():
        print(f"[WARN] Summary directory not found: {SUMMARY_DIR}")
        return out

    for f in sorted(SUMMARY_DIR.glob("*.csv")):
        with f.open("r", newline="", encoding="utf-8") as fh:
            reader = csv.DictReader(fh)
            for row in reader:
                for key in row:
                    if key not in fieldnames:
                        fieldnames.append(key)
                rows.append(row)

    if not rows:
        print("[ERROR] No summary files found in evaluation/summary/")
        return out

    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"[OK] Final comparison: {out} ({len(rows)} rows)")
    return out


# ═════════════════════════════════════════════════════════════════════════════
# Auto-discovery (all mode)
# ═════════════════════════════════════════════════════════════════════════════

# Convention for auto-discovery
_CASE_DISCOVERY = {
    "case1": {
        "gt": GROUND_TRUTH_DIR / "case1_windows_urls.csv",
        "chracer_result": EVAL_RESULTS_DIR / "case1_chracer_for_eval.csv",
        "regex_result": BASELINE_RESULTS_DIR / "case1_regex_urls.csv",
        "artifact_type": "url",
    },
    "case2": {
        "gt": GROUND_TRUTH_DIR / "case2_tab_groups.csv",
        "chracer_result": EVAL_RESULTS_DIR / "case2_chracer_for_eval.csv",
        "regex_result": BASELINE_RESULTS_DIR / "case2_regex_urls.csv",
        "artifact_type": "tab_group",
    },
    "case3": {
        "gt": GROUND_TRUTH_DIR / "case3_navigation_urls.csv",
        "chracer_result": EVAL_RESULTS_DIR / "case3_chracer_for_eval.csv",
        "regex_result": BASELINE_RESULTS_DIR / "case3_regex_urls.csv",
        "artifact_type": "url",
    },
}


def run_all() -> None:
    """Auto-discover and evaluate all cases, then compare."""
    print("=" * 60)
    print("  Chracer — Unified Evaluation Pipeline")
    print("=" * 60)
    print()

    for case_id, cfg in _CASE_DISCOVERY.items():
        gt = cfg["gt"]
        if not gt.exists():
            print(f"[SKIP] {case_id}: ground truth not found: {gt}")
            continue

        # ── Chracer eval ──
        chracer_result = cfg["chracer_result"]
        if not chracer_result.exists():
            # Try to auto-normalize from raw result in Chracer/result
            import sys
            if str(CHRACER_ROOT) not in sys.path:
                sys.path.insert(0, str(CHRACER_ROOT))
            import main
            raw_glob = f"{case_id}_lowmem_*.csv"
            raw_report = main.find_latest_report(raw_glob, CHRACER_ROOT / "result")
            if raw_report:
                print(f"[INFO] Auto-normalizing raw report: {raw_report.name}")
                main.report_rows_to_eval_csv(case_id, raw_report, chracer_result)

        if chracer_result.exists():
            print(f"\n--- {case_id} / Chracer ---")
            run_chracer_eval(
                case_id=case_id,
                gt_path=gt,
                result_path=chracer_result,
                artifact_type=cfg["artifact_type"],
            )
        else:
            print(f"[SKIP] {case_id} Chracer: result not found in evaluation/results/ and no raw report in result/")

        # ── Regex eval ──
        regex_result = cfg["regex_result"]
        if regex_result.exists():
            print(f"\n--- {case_id} / Regex ---")
            run_regex_eval(
                case_id=case_id,
                gt_path=gt,
                result_path=regex_result,
            )
        else:
            print(f"[SKIP] {case_id} Regex: result not found: {regex_result}")

    # ── Compare ──
    print(f"\n--- Final Comparison ---")
    run_compare()


# ═════════════════════════════════════════════════════════════════════════════
# CLI
# ═════════════════════════════════════════════════════════════════════════════

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Unified evaluation script for Chracer project.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""\
Examples:
    %(prog)s chracer --case case1 --gt ground_truth/case1_windows_urls.csv --result evaluation/results/case1_chracer_for_eval.csv
    %(prog)s regex   --case case1 --gt ground_truth/case1_windows_urls.csv --result baseline/results/case1_regex_urls.csv
    %(prog)s compare
    %(prog)s all
""",
    )
    sub = p.add_subparsers(dest="command", required=True)

    # ── chracer ──
    sp_chracer = sub.add_parser("chracer", help="Evaluate Chracer results vs ground truth")
    sp_chracer.add_argument("--case", required=True, help="Case ID (e.g. case1)")
    sp_chracer.add_argument("--gt", required=True, help="Ground truth CSV path")
    sp_chracer.add_argument("--result", required=True, help="Chracer result CSV path")
    sp_chracer.add_argument("--artifact-type", default=None, choices=["url", "tab_group"],
                            help="Artifact type (auto-detected from GT if omitted)")
    sp_chracer.add_argument("--tta-seconds", default="", help="Time-to-analysis in seconds")
    sp_chracer.add_argument("--log", default="", help="Log file path to auto-compute TTA")
    sp_chracer.add_argument("--out-detail", default=None, help="Detail CSV output path")
    sp_chracer.add_argument("--out-summary", default=None, help="Summary CSV output path")

    # ── regex ──
    sp_regex = sub.add_parser("regex", help="Evaluate Regex baseline results vs ground truth")
    sp_regex.add_argument("--case", required=True, help="Case ID (e.g. case1)")
    sp_regex.add_argument("--gt", required=True, help="Ground truth CSV path")
    sp_regex.add_argument("--result", required=True, help="Regex result CSV path")
    sp_regex.add_argument("--runtime-json", default="", help="Runtime JSON for TTA")
    sp_regex.add_argument("--out-detail", default=None, help="Detail CSV output path")
    sp_regex.add_argument("--out-summary", default=None, help="Summary CSV output path")

    # ── compare ──
    sp_compare = sub.add_parser("compare", help="Merge all summaries into final_compare.csv")
    sp_compare.add_argument("--output", default=None, help="Output CSV path")

    # ── all ──
    sub.add_parser("all", help="Auto-discover and evaluate all cases, then compare")

    return p


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "chracer":
        tta = args.tta_seconds
        if not tta and args.log:
            tta = parse_tta_from_log(Path(args.log))
        run_chracer_eval(
            case_id=args.case,
            gt_path=Path(args.gt),
            result_path=Path(args.result),
            artifact_type=args.artifact_type,
            tta_seconds=tta,
            out_detail=Path(args.out_detail) if args.out_detail else None,
            out_summary=Path(args.out_summary) if args.out_summary else None,
        )

    elif args.command == "regex":
        run_regex_eval(
            case_id=args.case,
            gt_path=Path(args.gt),
            result_path=Path(args.result),
            runtime_json=args.runtime_json,
            out_detail=Path(args.out_detail) if args.out_detail else None,
            out_summary=Path(args.out_summary) if args.out_summary else None,
        )

    elif args.command == "compare":
        run_compare(out_path=Path(args.output) if args.output else None)

    elif args.command == "all":
        run_all()


if __name__ == "__main__":
    main()

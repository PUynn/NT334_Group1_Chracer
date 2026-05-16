#!/usr/bin/env python3
import argparse
import csv
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit


def normalize_url(url: str) -> str:
    if url is None:
        return ""

    url = str(url).strip().replace("\x00", "")
    url = url.strip("\"'<>[]{}")

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


# Dùng để tránh đánh sai do Chromium redirect từ / sang /chromium-projects
URL_EQUIV = {
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
    a = normalize_url(a)
    b = normalize_url(b)

    if a == b:
        return True

    if a in URL_EQUIV and b in URL_EQUIV[a]:
        return True

    return False


def read_csv(path: Path):
    with path.open("r", newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def write_csv(path: Path, rows, fieldnames):
    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def get_url(row):
    for col in ["url_norm", "url_raw", "url"]:
        if col in row and row[col]:
            return normalize_url(row[col])
    return ""


def get_from_url(row):
    for col in ["from_url_norm", "from_url_raw", "referrer_norm", "referrer_raw", "from_raw"]:
        if col in row and row[col]:
            return normalize_url(row[col])
    return ""


def split_context(row):
    ctx = row.get("expected_context", "")
    if not ctx:
        return ["url"]

    return [x.strip() for x in ctx.split("+") if x.strip()]


def parse_tabs(value):
    if value is None:
        return set()

    value = str(value).strip().strip('"').strip("'")

    if not value:
        return set()

    return {x.strip() for x in value.split(",") if x.strip()}


def same_value(a, b):
    return str(a).strip().lower() == str(b).strip().lower()


def compute_url_completeness(gt, result):
    fields = split_context(gt)
    matched = []

    for field in fields:
        if field == "url":
            if is_equiv_url(get_url(gt), get_url(result)):
                matched.append(field)

        elif field in ["window", "window_index"]:
            if same_value(gt.get("window_index", ""), result.get("window_index", "")):
                matched.append(field)

        elif field in ["tab", "tab_index"]:
            if same_value(gt.get("tab_index", ""), result.get("tab_index", "")):
                matched.append(field)

        elif field in ["order", "nav_order"]:
            if same_value(gt.get("nav_order", ""), result.get("nav_order", "")):
                matched.append(field)

        elif field in ["from", "referrer"]:
            gt_from = get_from_url(gt)
            rs_from = get_from_url(result)
            if gt_from and rs_from and is_equiv_url(gt_from, rs_from):
                matched.append(field)

    completeness = len(matched) / len(fields) if fields else 0

    return completeness, "+".join(matched)


def compute_group_completeness(gt, result):
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


def evaluate_url(case_id, gt_rows, result_rows):
    details = []
    used_result_indexes = set()

    tp = 0
    fn = 0

    gt_url_rows = [r for r in gt_rows if r.get("artifact_type", "").lower() == "url"]
    result_url_rows = [r for r in result_rows if r.get("artifact_type", "").lower() == "url"]

    completeness_scores = []

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
                "note": "URL recovered by Chracer"
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
                "note": "Ground truth URL not recovered by Chracer"
            })

    fp = 0

    for idx, rs in enumerate(result_url_rows):
        if idx not in used_result_indexes:
            fp += 1
            details.append({
                "case_id": case_id,
                "artifact_id": "",
                "artifact_type": "url",
                "status": "FP",
                "expected": "",
                "recovered": get_url(rs),
                "expected_context": "",
                "matched_context": "",
                "completeness": 0,
                "note": "Chracer recovered URL not present in ground truth"
            })

    gt_total = len(gt_url_rows)
    recovered_total = len(result_url_rows)

    return details, gt_total, recovered_total, tp, fp, fn, completeness_scores


def evaluate_tab_group(case_id, gt_rows, result_rows):
    details = []
    used_result_indexes = set()

    tp = 0
    fn = 0

    gt_group_rows = [r for r in gt_rows if r.get("artifact_type", "").lower() == "tab_group"]
    result_group_rows = [r for r in result_rows if r.get("artifact_type", "").lower() == "tab_group"]

    completeness_scores = []

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
                "expected": f'{gt.get("group_name","")}:{gt.get("group_color","")}:{gt.get("tab_indexes","")}',
                "recovered": f'{rs.get("group_name","")}:{rs.get("group_color","")}:{rs.get("tab_indexes","")}',
                "expected_context": gt.get("expected_context", ""),
                "matched_context": matched_context,
                "completeness": round(completeness, 4),
                "note": "Tab group recovered by Chracer"
            })
        else:
            fn += 1
            completeness_scores.append(0)

            details.append({
                "case_id": case_id,
                "artifact_id": gt.get("artifact_id", ""),
                "artifact_type": "tab_group",
                "status": "FN",
                "expected": f'{gt.get("group_name","")}:{gt.get("group_color","")}:{gt.get("tab_indexes","")}',
                "recovered": "",
                "expected_context": gt.get("expected_context", ""),
                "matched_context": "",
                "completeness": 0,
                "note": "Ground truth tab group not recovered by Chracer"
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
                "recovered": f'{rs.get("group_name","")}:{rs.get("group_color","")}:{rs.get("tab_indexes","")}',
                "expected_context": "",
                "matched_context": "",
                "completeness": 0,
                "note": "Chracer recovered tab group not present in ground truth"
            })

    gt_total = len(gt_group_rows)
    recovered_total = len(result_group_rows)

    return details, gt_total, recovered_total, tp, fp, fn, completeness_scores


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--case-id", required=True)
    parser.add_argument("--gt", required=True)
    parser.add_argument("--result", required=True)
    parser.add_argument("--artifact-type", required=True, choices=["url", "tab_group"])
    parser.add_argument("--out-detail", required=True)
    parser.add_argument("--out-summary", required=True)
    parser.add_argument("--tta-seconds", default="")
    args = parser.parse_args()

    gt_rows = read_csv(Path(args.gt))
    result_rows = read_csv(Path(args.result))

    if args.artifact_type == "url":
        details, gt_total, recovered_total, tp, fp, fn, completeness_scores = evaluate_url(
            args.case_id, gt_rows, result_rows
        )
    else:
        details, gt_total, recovered_total, tp, fp, fn, completeness_scores = evaluate_tab_group(
            args.case_id, gt_rows, result_rows
        )

    recovery_rate = tp / gt_total if gt_total else 0
    fpr_noise_rate = fp / recovered_total if recovered_total else 0
    completeness = sum(completeness_scores) / len(completeness_scores) if completeness_scores else 0

    detail_fields = [
        "case_id",
        "artifact_id",
        "artifact_type",
        "status",
        "expected",
        "recovered",
        "expected_context",
        "matched_context",
        "completeness",
        "note",
    ]

    write_csv(Path(args.out_detail), details, detail_fields)

    summary = [{
        "case_id": args.case_id,
        "tool": "chracer",
        "artifact_type": args.artifact_type,
        "ground_truth_total": gt_total,
        "recovered_total": recovered_total,
        "TP": tp,
        "FP": fp,
        "FN": fn,
        "recovery_rate": round(recovery_rate, 4),
        "fpr_noise_rate": round(fpr_noise_rate, 4),
        "completeness": round(completeness, 4),
        "tta_seconds": args.tta_seconds,
        "note": "Chracer evaluation against ground truth"
    }]

    summary_fields = list(summary[0].keys())
    write_csv(Path(args.out_summary), summary, summary_fields)

    print("[OK] Chracer evaluation completed")
    print(summary[0])


if __name__ == "__main__":
    main()
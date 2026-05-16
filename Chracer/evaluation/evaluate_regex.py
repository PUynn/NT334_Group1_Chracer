#!/usr/bin/env python3
import argparse
import csv
import json
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

    # Chuẩn hóa dấu / cuối URL để so khớp ổn định hơn
    if path == "/":
        path = ""
    elif len(path) > 1 and path.endswith("/"):
        path = path.rstrip("/")

    # Bỏ fragment
    fragment = ""

    return urlunsplit((scheme, netloc, path, p.query, fragment))


def read_csv(path: Path):
    with path.open("r", newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def get_url(row):
    for col in ["url_norm", "url_raw", "url"]:
        if col in row and row[col]:
            return normalize_url(row[col])
    return ""


def get_runtime_seconds(runtime_path):
    if not runtime_path:
        return ""

    path = Path(runtime_path)
    if not path.exists():
        return ""

    try:
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        return data.get("runtime_seconds", "")
    except Exception:
        return ""


def expected_context_fields(row):
    ctx = row.get("expected_context", "")
    if not ctx:
        return ["url"]

    fields = [x.strip() for x in ctx.split("+") if x.strip()]
    return fields if fields else ["url"]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--case-id", required=True)
    parser.add_argument("--gt", required=True, help="Ground truth CSV")
    parser.add_argument("--result", required=True, help="Regex result CSV")
    parser.add_argument("--out-detail", required=True)
    parser.add_argument("--out-summary", required=True)
    parser.add_argument("--runtime-json", default="")
    args = parser.parse_args()

    gt_rows = read_csv(Path(args.gt))
    result_rows = read_csv(Path(args.result))

    # Chỉ đánh giá URL-level cho Regex
    gt_url_rows = [
        r for r in gt_rows
        if r.get("artifact_type", "").lower() == "url" and get_url(r)
    ]

    result_urls = {}
    for r in result_rows:
        u = get_url(r)
        if u:
            result_urls.setdefault(u, r)

    gt_urls = {get_url(r): r for r in gt_url_rows}

    detail_rows = []

    tp = 0
    fn = 0
    fp = 0
    completeness_scores = []

    # TP / FN
    for gt_url, gt_row in gt_urls.items():
        if gt_url in result_urls:
            status = "TP"
            tp += 1

            fields = expected_context_fields(gt_row)

            # Regex chỉ có URL, không có window/tab/order/from context
            matched_fields = 1 if "url" in fields else 0
            completeness = matched_fields / len(fields) if fields else 0

            completeness_scores.append(completeness)

            detail_rows.append({
                "case_id": args.case_id,
                "artifact_id": gt_row.get("artifact_id", ""),
                "status": status,
                "url_norm": gt_url,
                "expected_context": gt_row.get("expected_context", ""),
                "matched_context": "url",
                "completeness": round(completeness, 4),
                "note": "Regex found URL but has no tab/window/navigation context"
            })
        else:
            status = "FN"
            fn += 1
            completeness_scores.append(0)

            detail_rows.append({
                "case_id": args.case_id,
                "artifact_id": gt_row.get("artifact_id", ""),
                "status": status,
                "url_norm": gt_url,
                "expected_context": gt_row.get("expected_context", ""),
                "matched_context": "",
                "completeness": 0,
                "note": "Ground truth URL not found by Regex"
            })

    # FP
    for result_url in result_urls:
        if result_url not in gt_urls:
            fp += 1
            detail_rows.append({
                "case_id": args.case_id,
                "artifact_id": "",
                "status": "FP",
                "url_norm": result_url,
                "expected_context": "",
                "matched_context": "url",
                "completeness": 0,
                "note": "Regex recovered URL not present in ground truth"
            })

    gt_total = len(gt_urls)
    recovered_total = len(result_urls)

    recovery_rate = tp / gt_total if gt_total else 0
    fpr_noise_rate = fp / recovered_total if recovered_total else 0
    completeness_avg = (
        sum(completeness_scores) / len(completeness_scores)
        if completeness_scores else 0
    )

    tta = get_runtime_seconds(args.runtime_json)

    summary = {
        "case_id": args.case_id,
        "tool": "regex_baseline",
        "ground_truth_total": gt_total,
        "recovered_total": recovered_total,
        "TP": tp,
        "FP": fp,
        "FN": fn,
        "recovery_rate": round(recovery_rate, 4),
        "fpr_noise_rate": round(fpr_noise_rate, 4),
        "completeness": round(completeness_avg, 4),
        "tta_seconds": tta,
        "note": "Regex baseline only evaluates URL recovery, not tab/window/tab-group context"
    }

    # Write detail CSV
    detail_path = Path(args.out_detail)
    detail_path.parent.mkdir(parents=True, exist_ok=True)

    detail_fields = [
        "case_id",
        "artifact_id",
        "status",
        "url_norm",
        "expected_context",
        "matched_context",
        "completeness",
        "note"
    ]

    with detail_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=detail_fields)
        writer.writeheader()
        writer.writerows(detail_rows)

    # Write summary CSV
    summary_path = Path(args.out_summary)
    summary_path.parent.mkdir(parents=True, exist_ok=True)

    with summary_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(summary.keys()))
        writer.writeheader()
        writer.writerow(summary)

    print("[OK] Evaluation completed")
    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
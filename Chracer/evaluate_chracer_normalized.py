from pathlib import Path
from urllib.parse import urlsplit, urlunsplit
import csv 

OUT_DIR = Path("prototype/results")
OUT_DIR.mkdir(parents=True, exist_ok=True)

FIELDS = [
    "case_id",
    "tool",
    "artifact_type",
    "session_id",
    "window_index",
    "tab_index",
    "nav_order",
    "time",
    "title",
    "url_raw",
    "url_norm",
    "referrer_raw",
    "referrer_norm",
    "group_name",
    "group_color",
    "tab_indexes",
    "tab_count",
    "note",
]

def normalize_url(url: str) -> str:
    if not url:
        return ""

    url = url.strip().replace("\x00", "")
    url = url.strip("\"'<>[]{}")

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

def write_csv(filename, rows):
    path = OUT_DIR / filename
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    print(f"[OK] {path} - {len(rows)} rows")

# =========================
# Case 1 - Chracer normalized
# =========================

case1_rows = [
    {
        "case_id": "case1",
        "tool": "chracer",
        "artifact_type": "url",
        "session_id": "450578886",
        "window_index": "1",
        "tab_index": "1",
        "nav_order": "1",
        "time": "",
        "title": "Google",
        "url_raw": "https://www.google.com/",
        "url_norm": normalize_url("https://www.google.com/"),
        "referrer_raw": "",
        "referrer_norm": "",
        "group_name": "",
        "group_color": "",
        "tab_indexes": "",
        "tab_count": "",
        "note": "object_layout_result"
    },
    {
        "case_id": "case1",
        "tool": "chracer",
        "artifact_type": "url",
        "session_id": "450579008",
        "window_index": "2",
        "tab_index": "1",
        "nav_order": "1",
        "time": "",
        "title": "GitHub: Let’s build from here · GitHub",
        "url_raw": "https://github.com/",
        "url_norm": normalize_url("https://github.com/"),
        "referrer_raw": "",
        "referrer_norm": "",
        "group_name": "",
        "group_color": "",
        "tab_indexes": "",
        "tab_count": "",
        "note": "object_layout_result"
    },
    {
        "case_id": "case1",
        "tool": "chracer",
        "artifact_type": "url",
        "session_id": "450579010",
        "window_index": "3",
        "tab_index": "1",
        "nav_order": "1",
        "time": "",
        "title": "(4) YouTube",
        "url_raw": "https://www.youtube.com/",
        "url_norm": normalize_url("https://www.youtube.com/"),
        "referrer_raw": "",
        "referrer_norm": "",
        "group_name": "",
        "group_color": "",
        "tab_indexes": "",
        "tab_count": "",
        "note": "object_layout_result"
    },
    {
        "case_id": "case1",
        "tool": "chracer",
        "artifact_type": "url",
        "session_id": "450579012",
        "window_index": "4",
        "tab_index": "1",
        "nav_order": "1",
        "time": "",
        "title": "Home",
        "url_raw": "https://www.chromium.org/chromium-projects/",
        "url_norm": normalize_url("https://www.chromium.org/chromium-projects/"),
        "referrer_raw": "",
        "referrer_norm": "",
        "group_name": "",
        "group_color": "",
        "tab_indexes": "",
        "tab_count": "",
        "note": "object_layout_result; final_url_after_redirect"
    },
]

write_csv("case1_chracer_normalized.csv", case1_rows)

# =========================
# Case 2 - Chracer normalized
# =========================

case2_rows = [
    {
        "case_id": "case2",
        "tool": "chracer",
        "artifact_type": "tab_group",
        "session_id": "450577899",
        "window_index": "1",
        "tab_index": "",
        "nav_order": "",
        "time": "",
        "title": "",
        "url_raw": "",
        "url_norm": "",
        "referrer_raw": "",
        "referrer_norm": "",
        "group_name": "TabGroup1",
        "group_color": "yellow",
        "tab_indexes": "1,2",
        "tab_count": "2",
        "note": "object_layout_result"
    },
    {
        "case_id": "case2",
        "tool": "chracer",
        "artifact_type": "tab_group",
        "session_id": "450577899",
        "window_index": "1",
        "tab_index": "",
        "nav_order": "",
        "time": "",
        "title": "",
        "url_raw": "",
        "url_norm": "",
        "referrer_raw": "",
        "referrer_norm": "",
        "group_name": "TabGroup2",
        "group_color": "red",
        "tab_indexes": "3,4",
        "tab_count": "2",
        "note": "object_layout_result"
    },
    {
        "case_id": "case2",
        "tool": "chracer",
        "artifact_type": "tab_group",
        "session_id": "450577899",
        "window_index": "1",
        "tab_index": "",
        "nav_order": "",
        "time": "",
        "title": "",
        "url_raw": "",
        "url_norm": "",
        "referrer_raw": "",
        "referrer_norm": "",
        "group_name": "TabGroup3",
        "group_color": "grey",
        "tab_indexes": "5,6",
        "tab_count": "2",
        "note": "object_layout_result"
    },
    {
        "case_id": "case2",
        "tool": "chracer",
        "artifact_type": "tab_group",
        "session_id": "450577899",
        "window_index": "1",
        "tab_index": "",
        "nav_order": "",
        "time": "",
        "title": "",
        "url_raw": "",
        "url_norm": "",
        "referrer_raw": "",
        "referrer_norm": "",
        "group_name": "TabGroup4",
        "group_color": "blue",
        "tab_indexes": "7,8",
        "tab_count": "2",
        "note": "object_layout_result"
    },
]

write_csv("case2_chracer_normalized.csv", case2_rows)

# =========================
# Case 3 - Chracer normalized
# =========================

case3_data = [
    # tab 0 -> tab_index 1
    ("450578107", 1, 1, "1601-01-01 00:00:00", "", "https://www.wikipedia.org/", ""),
    ("450578107", 1, 2, "1601-01-01 00:00:00", "", "https://en.wikipedia.org/wiki/Digital_forensics", "https://www.wikipedia.org/"),
    ("450578107", 1, 3, "1601-01-01 00:00:00", "", "https://en.wikipedia.org/wiki/Computer_forensics", "https://en.wikipedia.org/wiki/Digital_forensics"),
    ("450578107", 1, 4, "1601-01-01 00:00:00", "", "https://en.wikipedia.org/wiki/Digital_evidence", "https://en.wikipedia.org/wiki/Computer_forensics"),
    ("450578107", 1, 5, "1601-01-01 00:00:00", "", "https://en.wikipedia.org/wiki/Best_evidence_rule", "https://en.wikipedia.org/wiki/Digital_evidence"),

    # tab 1 -> tab_index 2
    ("450578107", 2, 1, "1601-01-01 00:00:00", "", "https://www.chromium.org/chromium-projects/", "https://www.chromium.org/"),
    ("450578107", 2, 2, "1601-01-01 00:00:00", "", "https://www.chromium.org/Home/", "https://www.chromium.org/chromium-projects/"),
    ("450578107", 2, 3, "1601-01-01 00:00:00", "", "https://www.chromium.org/developers/", "https://www.chromium.org/Home/"),
    ("450578107", 2, 4, "1601-01-01 00:00:00", "", "https://www.chromium.org/developers/how-tos/getting-around-the-chrome-source-code/", "https://www.chromium.org/developers/"),
    ("450578107", 2, 5, "1601-01-01 00:00:00", "", "https://www.chromium.org/developers/design-documents/multi-process-architecture/", "https://www.chromium.org/developers/how-tos/getting-around-the-chrome-source-code/"),
]

case3_rows = []

for session_id, tab_index, nav_order, time_value, title, url_raw, referrer_raw in case3_data:
    case3_rows.append({
        "case_id": "case3",
        "tool": "chracer",
        "artifact_type": "url",
        "session_id": session_id,
        "window_index": "1",
        "tab_index": str(tab_index),
        "nav_order": str(nav_order),
        "time": time_value,
        "title": title,
        "url_raw": url_raw,
        "url_norm": normalize_url(url_raw),
        "referrer_raw": referrer_raw,
        "referrer_norm": normalize_url(referrer_raw),
        "group_name": "",
        "group_color": "",
        "tab_indexes": "",
        "tab_count": "",
        "note": "object_layout_result"
    })

write_csv("case3_chracer_normalized.csv", case3_rows)
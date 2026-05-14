
```text
NT334_Group1_Chracer/
├── Chracer/                     # Chracer tool
│   ├── main.py
│   ├── acquisition/
│   │   └── hash_dump.py
│   ├── baseline/
│   │   └── regex_extractor.py
│   └── prototype/
│       └── run_chracer.py       # Gọi Chracer
│
├── evaluation/
│   ├── evaluate_results.py
│   ├── ground_truth/            # File CSV ground truth
│   └── results/                 # Kết quả phân tích
│
├── reporting/
│   └── generate_report.py
│
├── dumps/                       # Memory dump
└── reports/                     # Báo cáo HTML/CSV/JSON
```

# Chracer-Based Chromium Memory Forensics

This project is based on the paper **“Chracer: Memory analysis of Chromium-based browsers”** by Geunyeong Choi, Jewan Bang, Sangjin Lee, and Jungheum Park, published at **DFRWS APAC 2023**.

A digital forensics project that analyzes memory dumps of Chromium-based browsers to recover web browsing artifacts, including visited URLs, tabs, browser windows, and Incognito/Private mode traces.

## Objectives

- Reproduce the core workflow of Chracer.
- Extract browser artifacts from Chromium memory dumps.
- Compare object-layout-based analysis with basic string-search methods.
- Evaluate recovery results using custom memory dump cases.

## Main Features
- Memory dump analysis for Chromium-based browsers.
- URL extraction from browser process memory.
- Tab/window reconstruction.
- Incognito/Private mode trace recovery.
- Baseline comparison using string-search.

## Dataset

The project uses:

- Original Chracer sample data.
- Custom memory dumps created by the group.


| Case | Description |
|---|---|
| C00 | Original Chracer dataset for sanity check |
| C01 | .... |
| C02 | ... |

## Team Members

| No. | Student ID | Full Name | Role |
|---|---|---|---|
| 1 | 23520144 | Trương Quốc Bảo| Team member |
| 2 | 23520501 | Đặng Hiểu Hòa | Team member |
| 3 | 23521761 | Lê Phương Uyên  | Team member |
| 4 | 23521828 | Lê Thị Tường Vy | Team member |

## References

- Choi, G., Bang, J., Lee, S., & Park, J. (2023). *Chracer: Memory analysis of Chromium-based browsers*. Forensic Science International: Digital Investigation.
- Original repository: https://github.com/geun-yeong/Chracer


```text
NT334_Group1_Chracer/
├── Chracer/                     
│   ├── main.py                  # Main pipeline script (Hash -> Scan -> Eval -> Report)
│   ├── acquisition/             # Hashing
│   ├── baseline/                # Independent Regex baseline tool
│   │   └── results/             # Baseline extraction outputs
│   ├── chracer/                 # Core memory analysis engine                          
│   │                 
│   ├── evaluation/              # Unified evaluation module
│   │   ├── details/             # Detailed eval metrics (TP/FP/FN)
│   │   └── summary/             # Aggregated summary reports
│   ├── ground_truth/            # Ground truth CSV datasets
│   ├── dumps/                   # Target memory dumps (.dmp)
│   ├── result/                  # Temporary Chracer extraction results
│   └── symbols/                 # Chromium symbols cache
├── reporting/                   # Report generation logic
└── reports/                     # Final generated reports (HTML/CSV/JSON)
```

# Chracer-Based Chromium Memory Forensics

This project is based on the paper **“Chracer: Memory analysis of Chromium-based browsers”** by Geunyeong Choi, Jewan Bang, Sangjin Lee, and Jungheum Park, published at **DFRWS APAC 2023**.

A digital forensics project that analyzes memory dumps of Chromium-based browsers to recover web browsing artifacts, including visited URLs, tabs, browser windows, and Incognito/Private mode traces.

## Objectives

- Reproduce the Chracer memory forensics framework for Chromium-based browsers.
- Recover browser artifacts from process memory using object layout analysis.
- Compare object-layout-based reconstruction against Regex-based memory searching.
- Evaluate forensic recovery performance using ground-truth datasets.

## Features

- Chromium memory dump analysis
- Browser object carving
- Pointer traversal reconstruction
- URL and page title recovery
- Tab, Tab Group, and window reconstruction
- Incognito/Private mode detection
- Evidence integrity verification (MD5/SHA-256)
- Automated forensic evaluation
- CSV/JSON report generation

## Contributions

- **XML-to-Pickle optimization** for object-layout loading 
- Ground-truth-based evaluation framework
- Automated forensic metrics calculation 
- Structured forensic reporting **with investigation logs**

## Dataset

The project uses:
| Case | Description |
|---|---|
| C00 | Original Chracer dataset for sanity check. |
| C01 | **Window and URL Recovery**: 4 separate Chromium windows, each accessing 1 unique URL (Google, GitHub, YouTube, Chromium). |
| C02 | **Tab Group Reconstruction**: 1 window containing 8 tabs organized into 4 tab groups (TabGroup1-4) with assigned colors (yellow, red, grey, blue). |
| C03 | **Tab-specific Navigation URL Recovery**: 1 window with 2 tabs. Tab 1 navigated to 5 Wikipedia URLs; Tab 2 navigated to 5 Chromium URLs. |

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

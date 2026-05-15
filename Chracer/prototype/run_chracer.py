#!/usr/bin/env python3
import subprocess
import time
import os
import glob
import csv
from pathlib import Path

# 1. KHAI BÁO ĐƯỜNG DẪN DỰA TRÊN CẤU TRÚC THƯ MỤC
# File này đang ở: NT334_Group1_Chracer/Chracer/prototype/run_chracer.py
PROTOTYPE_DIR = Path(__file__).resolve().parent
CHRACER_DIR = PROTOTYPE_DIR.parent
PROJECT_ROOT = CHRACER_DIR.parent

# Các thư mục liên quan
EVAL_RESULTS_DIR = PROJECT_ROOT / 'evaluation' / 'results'
REPORTS_DIR = PROJECT_ROOT / 'reports'
DUMPS_DIR = PROJECT_ROOT / 'dumps'

def run_prototype(target_case="case1_lowmem_1.py", dump_name="case1.dmp"):
    script_to_run = CHRACER_DIR / target_case
    dump_file = DUMPS_DIR / dump_name

    if not script_to_run.exists():
        print(f"[!] Không tìm thấy script: {script_to_run}")
        return
    if not dump_file.exists():
        print(f"[!] Không tìm thấy file dump: {dump_file}")
        return

    # Tạo thư mục chứa kết quả đánh giá nếu chưa có
    EVAL_RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    print(f"[*] ĐANG CHẠY PROTOTYPE (CHRACER) TRÊN DỮ LIỆU: {dump_file.name}...")
    
    # --- BẮT ĐẦU ĐO THỜI GIAN (TIME-TO-ANALYSIS) ---
    start_time = time.perf_counter()

    # Chạy script case1 bằng subprocess
    # Cú pháp: python3 case1_lowmem_1.py --dump dumps/case1.dmp
    cmd = ["python3", str(script_to_run), "--dump", str(dump_file)]
    
    try:
        # Chạy và chờ script hoàn thành
        subprocess.run(cmd, check=True)
    except subprocess.CalledProcessError as e:
        print(f"[!] Có lỗi xảy ra khi chạy Chracer: {e}")
        return

    # --- KẾT THÚC ĐO THỜI GIAN ---
    end_time = time.perf_counter()
    execution_time = end_time - start_time
    print(f"\n[*] HOÀN THÀNH PROTOTYPE!")
    print(f"[*] Thời gian thực thi (Time-to-analysis): {execution_time:.4f} giây.")

    # Lưu thời gian vào file txt để module Evaluation đọc
    time_file = EVAL_RESULTS_DIR / "prototype_time.txt"
    with open(time_file, "w", encoding="utf-8") as f:
        f.write(str(execution_time))

    # --- CHUẨN HÓA DỮ LIỆU ĐỂ ĐÁNH GIÁ ---
    print("[*] Đang chuẩn hóa dữ liệu đầu ra để đưa vào module Đánh giá...")
    
    # Tìm file CSV mới nhất do case1 vừa sinh ra trong thư mục reports/
    search_pattern = str(REPORTS_DIR / '*_report_*.csv')
    list_of_csv = glob.glob(search_pattern)
    
    if not list_of_csv:
        print("[!] Không tìm thấy file CSV báo cáo nào trong thư mục reports/.")
        return
        
    latest_csv = max(list_of_csv, key=os.path.getctime)
    
    extracted_data = []
    # Đọc file báo cáo gốc
    with open(latest_csv, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            # Lọc bỏ các URL "N/A" hoặc trống (nếu có)
            if row.get('URL') and row['URL'] != "N/A":
                extracted_data.append({
                    'URL': row['URL'],
                    'Title': row.get('Title', 'N/A')
                })

    # Lưu lại thành 1 file CSV chuẩn chỉ chứa URL và Title cho việc Evaluation
    eval_csv = EVAL_RESULTS_DIR / "prototype_extracted.csv"
    with open(eval_csv, 'w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=['URL', 'Title'])
        writer.writeheader()
        writer.writerows(extracted_data)

    print(f"[*] Đã trích xuất {len(extracted_data)} URLs.")
    print(f"[*] Dữ liệu Prototype đã sẵn sàng tại: {eval_csv}")

if __name__ == "__main__":
    # Bạn có thể đổi tên case và file dump tùy ý ở đây
    run_prototype(target_case="case1_lowmem_1.py", dump_name="case1.dmp")
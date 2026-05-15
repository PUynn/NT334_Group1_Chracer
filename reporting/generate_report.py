import csv
import json
import os
from datetime import datetime

def export_csv(data, headers, output_path):
    """Xuất dữ liệu ra file CSV"""
    with open(output_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(headers)
        writer.writerows(data)

def export_json(data, headers, metadata, output_path):
    """Xuất dữ liệu ra file JSON, gộp chung với Metadata chứng cứ"""
    records = []
    for row in data:
        # Map từng cột header với giá trị tương ứng
        records.append(dict(zip(headers, [str(item) for item in row])))
    
    report = {
        "chain_of_custody_metadata": metadata,
        "extracted_artifacts": records
    }
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=4, ensure_ascii=False)

def export_html(data, headers, metadata, output_path):
    """Tạo báo cáo HTML chuyên nghiệp chuẩn Pháp chứng Kỹ thuật số"""
    html_content = f"""
    <!DOCTYPE html>
    <html lang="vi">
    <head>
        <meta charset="UTF-8">
        <title>Báo Cáo Điều Tra Số - Digital Forensics Report</title>
        <style>
            body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; margin: 40px; color: #333; }}
            h1 {{ color: #2c3e50; border-bottom: 2px solid #3498db; padding-bottom: 10px; }}
            h2 {{ color: #2980b9; margin-top: 30px; }}
            .metadata-box {{ background-color: #f8f9fa; border-left: 5px solid #e74c3c; padding: 15px; margin-bottom: 20px; }}
            .metadata-box p {{ margin: 5px 0; }}
            table {{ border-collapse: collapse; width: 100%; margin-top: 15px; box-shadow: 0 2px 5px rgba(0,0,0,0.1); }}
            th, td {{ border: 1px solid #ddd; padding: 12px; text-align: left; }}
            th {{ background-color: #34495e; color: white; }}
            tr:nth-child(even) {{ background-color: #f2f2f2; }}
            tr:hover {{ background-color: #e8f4f8; }}
        </style>
    </head>
    <body>
        <h1>Báo Cáo Điều Tra Số (Memory Forensics)</h1>
        
        <div class="metadata-box">
            <h2>Bảo Toàn Chứng Cứ (Chain of Custody)</h2>
            <p><strong>Tên file gốc:</strong> {metadata.get('file_name', 'N/A')}</p>
            <p><strong>Dung lượng:</strong> {metadata.get('file_size_bytes', 'N/A')} bytes</p>
            <p><strong>Thời gian phân tích:</strong> {metadata.get('analysis_start_time', 'N/A')}</p>
            <p><strong>MD5 Hash:</strong> <code>{metadata.get('md5_hash', 'N/A')}</code></p>
            <p><strong>SHA256 Hash:</strong> <code>{metadata.get('sha256_hash', 'N/A')}</code></p>
        </div>

        <h2>Dữ Liệu Trích Xuất (Extracted Artifacts)</h2>
        <table>
            <tr>
                {"".join([f"<th>{h}</th>" for h in headers])}
            </tr>
    """
    
    # Đổ dữ liệu vào bảng HTML
    for row in data:
        html_content += "<tr>"
        for item in row:
            html_content += f"<td>{item}</td>"
        html_content += "</tr>"
        
    html_content += """
        </table>
    </body>
    </html>
    """
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html_content)

def generate_all_reports(case_name, headers, data, metadata_file_path, output_dir="result"):
    """Hàm tổng điều khiển việc xuất 3 loại file"""
    # 1. Đọc metadata chứng cứ từ file JSON do Cải tiến 1 sinh ra
    metadata = {}
    if os.path.exists(metadata_file_path):
        with open(metadata_file_path, 'r', encoding='utf-8') as f:
            metadata = json.load(f)
    else:
        print(f"[CẢNH BÁO] Không tìm thấy file metadata tại: {metadata_file_path}")
    
    # 2. Tạo thư mục và định dạng tên file
    os.makedirs(output_dir, exist_ok=True)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    base_filename = f"{case_name}_{timestamp}"
    
    csv_path = os.path.join(output_dir, f"{base_filename}.csv")
    json_path = os.path.join(output_dir, f"{base_filename}.json")
    html_path = os.path.join(output_dir, f"{base_filename}.html")
    
    # 3. Xuất file
    export_csv(data, headers, csv_path)
    export_json(data, headers, metadata, json_path)
    export_html(data, headers, metadata, html_path)
    
    return csv_path, json_path, html_path
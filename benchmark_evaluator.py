#!/usr/bin/env python3
"""
Automated 200 Sites Benchmark & Evaluation Engine for Thesis Research.
Probes synthetic websites, extracts multi-signals, evaluates Configuration 2 (Multi-signal Rule & Correlation),
compares against ground truth categories, and calculates Accuracy, Precision, Recall, F1, and Noise Reduction.
"""

import os
import sys
import json
import csv
import time
import argparse
from pathlib import Path
from typing import Dict, Any, List
from collections import defaultdict

# Fix UTF-8 output on Windows
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

# Add assistant directory to path
BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

from tools.http_checker import check_http
from tools.dns_checker import check_dns
from tools.ssl_checker import check_ssl
from tools.dom_validator import validate_dom
from analytics.rule_engine import RuleBasedAnomalyEngine
from analytics.correlation_engine import RuleBasedCorrelationEngine
from analytics.anomaly_detector import AnomalyDetectionOrchestrator

# Paths
DATASET_DIR = BASE_DIR.parent / "dataset"
GROUND_TRUTH_CSV = DATASET_DIR / "ground_truth.csv"
TARGET_WEBSITES_JSON = BASE_DIR / "target_websites.json"

def load_targets() -> List[Dict[str, Any]]:
    if not TARGET_WEBSITES_JSON.exists():
        print(f"[!] {TARGET_WEBSITES_JSON} not found!")
        return []
    with open(TARGET_WEBSITES_JSON, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data.get("websites", [])

def map_incident_to_category(incident_type: str, http_res: dict, dns_res: dict, ssl_res: dict, dom_res: dict = None) -> str:
    """Map Rule Engine / Correlation output back to Ground Truth Category theo thứ bậc SRE / OSI."""
    status_code = http_res.get("status_code")
    err_type = http_res.get("error_type")
    resp_time = http_res.get("response_time_ms", 0.0)

    # 1. Lỗi phân giải DNS (Lớp cơ sở mạng L3/L7)
    if dns_res.get("resolved") is False or incident_type in ["DNS_RESOLUTION_OUTAGE", "DNS_RESOLUTION_FAILED", "DNS_FAILURE"]:
        return "DNS_FAILURE"

    # 2. Lỗi chứng chỉ SSL (Lớp bảo mật TLS L6)
    if ssl_res.get("is_expired") or incident_type in ["SSL_CERT_EXPIRED", "SSL_CERTIFICATE_EXPIRED"]:
        return "SSL_EXPIRED"
    if (ssl_res.get("hostname_matched") is False and not ssl_res.get("is_http_only")) or incident_type in ["SSL_HOST_MISMATCH", "SSL_HOSTNAME_MISMATCH", "SSL_UNTRUSTED_CA", "SSL_UNTRUSTED_ISSUER"]:
        return "SSL_INVALID"

    # 3. Vòng lặp chuyển hướng (Redirect Loop)
    if (http_res.get("is_redirect_loop") or 
        (http_res.get("redirect_chain") and len(http_res.get("redirect_chain", [])) >= 5) or 
        err_type == "TooManyRedirects" or 
        incident_type == "HTTP_REDIRECT_LOOP_DETECTED"):
        return "REDIRECT_LOOP"

    # 4. Lỗi code Ứng dụng Backend (500)
    if status_code == 500 or incident_type in ["BACKEND_APPLICATION_ERROR", "HTTP_500_INTERNAL_ERROR"]:
        return "BACKEND_500"

    # 5. Lỗi hạ tầng máy chủ ngưng hoạt động (502, 503, 504 hoặc Connection Refused)
    if (status_code in [502, 503, 504] or 
        http_res.get("can_connect") is False or 
        incident_type in ["SERVER_PROCESS_DOWN", "HTTP_5XX_SERVER_DOWN", "HTTP_CONNECTIVITY_OUTAGE"]):
        return "SERVER_DOWN"

    # 6. Lỗi suy giảm hiệu năng / Độ trễ cao (Kiểm tra trước DOM vì nếu server quá trễ, DOM sẽ không thể tải kịp)
    if (err_type == "Timeout" or 
        resp_time >= 5000 or 
        incident_type in ["PERFORMANCE_DEGRADATION", "PERF_CRITICAL_LATENCY", "PERF_DEGRADED_LATENCY", "STAT_Z_SCORE_SPIKE", "SRE_LATENCY_VIOLATION"]):
        return "HIGH_LATENCY"

    # 7. Lỗi cấu trúc DOM
    if (dom_res and not dom_res.get("is_structure_valid", True)) or incident_type in ["FRONTEND_UI_DEFORMATION", "DOM_STRUCTURAL_CORRUPTION", "DOM_STRUCTURE_CORRUPTED", "MISSING_DOM"]:
        return "MISSING_DOM"

    if not incident_type or incident_type == "NO_INCIDENT":
        return "NORMAL"
        
    mapping = {
        "BACKEND_APPLICATION_ERROR": "BACKEND_500",
        "HTTP_500_INTERNAL_ERROR": "BACKEND_500",
        "HTTP_5XX_SERVER_ERROR": "BACKEND_500",
        "BACKEND_500": "BACKEND_500",
        
        "PERFORMANCE_DEGRADATION": "HIGH_LATENCY",
        "HIGH_LATENCY": "HIGH_LATENCY",
        
        "SERVER_PROCESS_DOWN": "SERVER_DOWN",
        "HTTP_5XX_SERVER_DOWN": "SERVER_DOWN",
        "SERVER_DOWN": "SERVER_DOWN",
        
        "REDIRECT_LOOP": "REDIRECT_LOOP",
        "DNS_FAILURE": "DNS_FAILURE",
        "SSL_EXPIRED": "SSL_EXPIRED",
        "SSL_INVALID": "SSL_INVALID",
        "MISSING_DOM": "MISSING_DOM",
        "NO_INCIDENT": "NORMAL"
    }
    return mapping.get(incident_type, incident_type)

def calculate_metrics(results: List[Dict[str, Any]]):
    """Tính toán Precision, Recall, F1 theo từng nhóm sự cố."""
    categories = sorted(list(set([r["ground_truth_category"] for r in results] + [r["detected_category"] for r in results])))
    
    tp = defaultdict(int)
    fp = defaultdict(int)
    fn = defaultdict(int)
    tn = defaultdict(int)
    
    for r in results:
        gt = r["ground_truth_category"]
        pred = r["detected_category"]
        for cat in categories:
            if gt == cat and pred == cat:
                tp[cat] += 1
            elif gt != cat and pred == cat:
                fp[cat] += 1
            elif gt == cat and pred != cat:
                fn[cat] += 1
            else:
                tn[cat] += 1

    print("\n" + "="*80)
    print("📈 BẢNG ĐÁNH GIÁ CHI TIẾT THEO TỪNG NHÓM SỰ CỐ (PER-CLASS CLASSIFICATION METRICS)")
    print("="*80)
    print(f"{'Nhóm Sự Cố':<18} | {'Support':<8} | {'Precision':<10} | {'Recall':<10} | {'F1-Score':<10}")
    print("-" * 65)

    weighted_f1_sum = 0
    total_samples = len(results)

    for cat in categories:
        support = tp[cat] + fn[cat]
        if support == 0 and fp[cat] == 0:
            continue
        p = tp[cat] / (tp[cat] + fp[cat]) if (tp[cat] + fp[cat]) > 0 else 0.0
        r = tp[cat] / (tp[cat] + fn[cat]) if (tp[cat] + fn[cat]) > 0 else 0.0
        f1 = (2 * p * r) / (p + r) if (p + r) > 0 else 0.0
        weighted_f1_sum += f1 * support
        print(f"{cat:<18} | {support:<8} | {p*100:>8.1f}% | {r*100:>8.1f}% | {f1*100:>8.1f}%")

    weighted_f1 = (weighted_f1_sum / total_samples) * 100 if total_samples > 0 else 0.0
    print("-" * 65)
    print(f"{'WEIGHTED AVERAGE':<18} | {total_samples:<8} | {'-':<10} | {'-':<10} | {weighted_f1:>8.1f}%")
    print("="*80)

def run_benchmark(limit: int = None, start_idx: int = 0):
    targets = load_targets()
    if not targets:
        print("[-] No targets available to benchmark.")
        return

    if limit:
        targets = targets[start_idx : start_idx + limit]

    orchestrator = AnomalyDetectionOrchestrator()

    print(f"\n=======================================================")
    print(f"📊 STARTING BENCHMARK EVALUATION ({len(targets)} Websites)")
    print(f"=======================================================\n")

    results = []
    correct_count = 0
    total_time = 0.0
    total_raw_alerts = 0
    total_correlated_incidents = 0

    print(f"{'Site ID':<10} | {'Domain':<24} | {'Ground Truth':<16} | {'Detected Issue':<16} | {'Match':<6} | {'Time (ms)':<10}")
    print("-" * 92)

    for site in targets:
        meta = site.get("metadata", {})
        expected_cat = meta.get("fault_category", "UNKNOWN")
        url = site.get("url")
        domain = site.get("domain")
        baseline_dns = site.get("baseline_dns", {})

        t0 = time.time()
        # 1. Run Checkers với timeout mở rộng 12s cho các site High Latency
        http_res = check_http(url, timeout=12.0)
        dns_res = check_dns(domain, baseline=baseline_dns, timeout=3.0)
        ssl_res = check_ssl(url, timeout=3.0)

        # 1b. Run DOM check nhanh qua BS4 parser
        dom_res = None
        if http_res.get("status_code") == 200:
            try:
                dom_res = validate_dom(url, use_browser=False, timeout=3.0)
            except Exception:
                dom_res = None

        # 2. Run Orchestrator (Multi-Signal Rules + Statistical + Correlation)
        analysis = orchestrator.run_multi_signal_rule_statistical(
            http_res=http_res,
            dns_res=dns_res,
            ssl_res=ssl_res,
            dom_res=dom_res,
            history_latencies=[]
        )
        incident_type = analysis.get("incident_type", "NO_INCIDENT")

        # 3. Map detected category
        detected_cat = map_incident_to_category(incident_type, http_res, dns_res, ssl_res, dom_res=dom_res)
        elapsed_ms = round((time.time() - t0) * 1000, 2)
        total_time += elapsed_ms

        is_match = (expected_cat == detected_cat)
        if is_match:
            correct_count += 1

        # Cảnh báo thô vs Sự cố tương quan
        raw_violations = len(analysis.get("all_violations", []))
        total_raw_alerts += raw_violations
        if analysis.get("is_anomaly_detected"):
            total_correlated_incidents += 1

        match_str = "✅ YES" if is_match else "❌ NO"
        site_id = meta.get("site_id", site.get("name", "N/A"))

        print(f"{site_id:<10} | {domain:<24} | {expected_cat:<16} | {detected_cat:<16} | {match_str:<6} | {elapsed_ms:<10}")

        results.append({
            "site_id": site_id,
            "domain": domain,
            "url": url,
            "ground_truth_category": expected_cat,
            "detected_category": detected_cat,
            "incident_type": incident_type,
            "is_correct": is_match,
            "anomaly_score": analysis.get("anomaly_score", 0),
            "http_status": http_res.get("status_code"),
            "response_time_ms": http_res.get("response_time_ms"),
            "dns_resolved": dns_res.get("resolved"),
            "ssl_valid": ssl_res.get("is_valid"),
            "scan_duration_ms": elapsed_ms
        })

    # Summary Metrics
    accuracy = round((correct_count / len(targets)) * 100, 2)
    avg_latency = round(total_time / len(targets), 2)
    noise_reduction = round(((total_raw_alerts - total_correlated_incidents) / total_raw_alerts * 100), 2) if total_raw_alerts > 0 else 0.0

    print("\n=======================================================")
    print(f"🎯 BENCHMARK RESULTS SUMMARY (CẤU HÌNH 2 vs GROUND TRUTH):")
    print(f"   • Total Scanned Websites: {len(targets)}")
    print(f"   • Correct Detections:     {correct_count} / {len(targets)}")
    print(f"   • Overall Accuracy Rate:  {accuracy}%")
    print(f"   • Noise Reduction Rate:   {noise_reduction}% (Suppressed Alert Storm)")
    print(f"   • Avg Scan Time (Latency):{avg_latency} ms per site")
    print(f"=======================================================")

    # Classification Metrics Table
    calculate_metrics(results)

    # Export to CSV
    out_csv = BASE_DIR / "benchmark_report.csv"
    try:
        with open(out_csv, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=list(results[0].keys()))
            writer.writeheader()
            writer.writerows(results)
        print(f"\n[✓] Đã xuất báo cáo chi tiết kết quả benchmark vào file: {out_csv}")
    except PermissionError:
        timestamp = int(time.time())
        fallback_csv = BASE_DIR / f"benchmark_report_{timestamp}.csv"
        try:
            with open(fallback_csv, "w", encoding="utf-8", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=list(results[0].keys()))
                writer.writeheader()
                writer.writerows(results)
            print(f"\n[⚠️] File '{out_csv.name}' đang bị khóa bởi Excel/Editor. Đã lưu dự phòng vào: {fallback_csv}")
        except Exception as e:
            print(f"\n[!] Không thể ghi file CSV: {e}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run 200 sites benchmark evaluation")
    parser.add_argument("--limit", type=int, default=None, help="Number of sites to test (e.g. --limit 20)")
    parser.add_argument("--start", type=int, default=0, help="Start index (e.g. --start 0)")
    args = parser.parse_args()
    run_benchmark(limit=args.limit, start_idx=args.start)

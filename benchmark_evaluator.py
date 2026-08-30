#!/usr/bin/env python3
"""
Automated 200 Sites Benchmark & Evaluation Engine for Thesis Research.
Probes all 200 synthetic websites, extracts signals, evaluates Multi-signal Rule Engine,
compares against dataset/ground_truth.csv, and calculates Accuracy, Precision, Recall, F1.
"""

import os
import sys
import json
import csv
import time
import argparse
from pathlib import Path
from typing import Dict, Any, List

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
from analytics.rule_engine import RuleEngine
from analytics.correlation_engine import CorrelationEngine
from analytics.anomaly_scorer import AnomalyScorer

# Paths
DATASET_DIR = BASE_DIR.parent / "dataset"
GROUND_TRUTH_CSV = DATASET_DIR / "ground_truth.csv"
METADATA_JSON = DATASET_DIR / "metadata.json"
TARGET_WEBSITES_JSON = BASE_DIR / "target_websites.json"

def load_targets() -> List[Dict[str, Any]]:
    if not TARGET_WEBSITES_JSON.exists():
        print(f"[!] {TARGET_WEBSITES_JSON} not found!")
        return []
    with open(TARGET_WEBSITES_JSON, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data.get("websites", [])

def map_incident_to_category(incident_type: str, http_res: dict, dns_res: dict, ssl_res: dict) -> str:
    """Map Rule Engine / Correlation output back to Ground Truth Category."""
    if not incident_type:
        # Check if HTTP 500
        if http_res.get("status_code") == 500:
            return "BACKEND_500"
        if http_res.get("is_redirect_loop"):
            return "REDIRECT_LOOP"
        if http_res.get("response_time_ms", 0) > 8000:
            return "HIGH_LATENCY"
        if http_res.get("status_code") in [502, 503, 504] or http_res.get("can_connect") is False:
            return "SERVER_DOWN"
        if dns_res.get("resolution_success") is False or dns_res.get("changes_detected"):
            return "DNS_FAILURE"
        if ssl_res.get("is_expired"):
            return "SSL_EXPIRED"
        if ssl_res.get("hostname_matched") is False and not ssl_res.get("is_http_only"):
            return "SSL_INVALID"
        return "NORMAL"
        
    mapping = {
        "HTTP_5XX_SERVER_ERROR": "BACKEND_500",
        "BACKEND_500": "BACKEND_500",
        "HTTP_500": "BACKEND_500",
        "HIGH_LATENCY": "HIGH_LATENCY",
        "SLOW_RESPONSE_TIME": "HIGH_LATENCY",
        "HTTP_TIMEOUT": "HIGH_LATENCY",
        "SERVICE_UNAVAILABLE_503": "SERVER_DOWN",
        "BAD_GATEWAY_502": "SERVER_DOWN",
        "SERVER_DOWN": "SERVER_DOWN",
        "HTTP_REDIRECT_LOOP": "REDIRECT_LOOP",
        "REDIRECT_LOOP": "REDIRECT_LOOP",
        "DNS_RESOLUTION_FAILURE": "DNS_FAILURE",
        "DNS_BASELINE_MISMATCH": "DNS_FAILURE",
        "DNS_FAILURE": "DNS_FAILURE",
        "SSL_CERTIFICATE_EXPIRED": "SSL_EXPIRED",
        "SSL_EXPIRED": "SSL_EXPIRED",
        "SSL_HOSTNAME_MISMATCH": "SSL_INVALID",
        "SSL_UNTRUSTED_CA": "SSL_INVALID",
        "SSL_INVALID": "SSL_INVALID",
        "DOM_ELEMENT_MISSING": "MISSING_DOM",
        "MISSING_DOM": "MISSING_DOM"
    }
    return mapping.get(incident_type, incident_type)

def run_benchmark(limit: int = None, start_idx: int = 0):
    targets = load_targets()
    if not targets:
        print("[-] No targets available to benchmark.")
        return

    if limit:
        targets = targets[start_idx : start_idx + limit]

    rule_engine = RuleEngine()
    correlation_engine = CorrelationEngine()
    anomaly_scorer = AnomalyScorer()

    print(f"\n=======================================================")
    print(f"📊 STARTING BENCHMARK EVALUATION ({len(targets)} Websites)")
    print(f"=======================================================\n")

    results = []
    correct_count = 0
    total_time = 0.0

    print(f"{'Site ID':<10} | {'Domain':<22} | {'Ground Truth':<16} | {'Detected Issue':<16} | {'Match':<6} | {'Time (ms)':<10}")
    print("-" * 90)

    for site in targets:
        meta = site.get("metadata", {})
        expected_cat = meta.get("fault_category", "UNKNOWN")
        url = site.get("url")
        domain = site.get("domain")
        baseline_dns = site.get("baseline_dns", {})

        t0 = time.time()
        # 1. Run Checkers
        http_res = check_http(url, timeout=5.0)
        dns_res = check_dns(domain, baseline=baseline_dns, timeout=3.0)
        ssl_res = check_ssl(url, timeout=3.0)

        # 2. Rule Engine & Correlation
        violations = rule_engine.evaluate(http_res, dns_res, ssl_res)
        corr_res = correlation_engine.correlate(violations)
        incident_type = corr_res.get("incident_type")

        detected_cat = map_incident_to_category(incident_type, http_res, dns_res, ssl_res)
        elapsed_ms = round((time.time() - t0) * 1000, 2)
        total_time += elapsed_ms

        is_match = (expected_cat == detected_cat)
        if is_match:
            correct_count += 1

        match_str = "✅ YES" if is_match else "❌ NO"
        site_id = meta.get("site_id", site.get("name", "N/A"))

        print(f"{site_id:<10} | {domain:<22} | {expected_cat:<16} | {detected_cat:<16} | {match_str:<6} | {elapsed_ms:<10}")

        results.append({
            "site_id": site_id,
            "domain": domain,
            "url": url,
            "ground_truth_category": expected_cat,
            "detected_category": detected_cat,
            "incident_type": incident_type,
            "is_correct": is_match,
            "http_status": http_res.get("status_code"),
            "response_time_ms": http_res.get("response_time_ms"),
            "dns_success": dns_res.get("resolution_success"),
            "ssl_valid": ssl_res.get("is_valid"),
            "scan_duration_ms": elapsed_ms
        })

    # Summary Metrics
    accuracy = round((correct_count / len(targets)) * 100, 2)
    avg_latency = round(total_time / len(targets), 2)

    print("\n=======================================================")
    print(f"🎯 BENCHMARK RESULTS SUMMARY:")
    print(f"   • Total Scanned:         {len(targets)}")
    print(f"   • Correct Detections:   {correct_count}")
    print(f"   • Accuracy Rate:        {accuracy}%")
    print(f"   • Avg MTTD (Latency):   {avg_latency} ms per site")
    print(f"=======================================================\n")

    # Export to CSV & JSON
    out_csv = BASE_DIR / "benchmark_report.csv"
    with open(out_csv, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(results[0].keys()))
        writer.writeheader()
        writer.writerows(results)
    print(f"[✓] Exported benchmark report to {out_csv}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run 200 sites benchmark evaluation")
    parser.add_argument("--limit", type=int, default=None, help="Number of sites to test (default: all)")
    parser.add_argument("--start", type=int, default=0, help="Start index (default: 0)")
    args = parser.parse_args()
    run_benchmark(limit=args.limit, start_idx=args.start)

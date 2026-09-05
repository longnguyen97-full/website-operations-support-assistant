import json
import sqlite3
import re
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

BASE_DIR = Path(__file__).resolve().parent.parent
TARGET_FILE = BASE_DIR / "target_websites.json"
DB_FILE = BASE_DIR / "data" / "monitoring.db"

def extract_site_num(name_or_domain: str) -> int:
    match = re.search(r"site[-_]?(\d+)", name_or_domain, re.IGNORECASE)
    if match:
        return int(match.group(1))
    return 0

from collections import defaultdict

def partition_baselines():
    print("🚀 Bắt đầu phân bổ Baseline phân tầng (Stratified 50/50) đều theo từng nhóm sự cố...")

    # 1. Cập nhật target_websites.json
    with open(TARGET_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    websites = data.get("websites", [])
    
    # Nhóm các website theo nhóm sự cố (Fault Category)
    category_sites = defaultdict(list)
    for site in websites:
        cat = site.get("metadata", {}).get("fault_category", "UNKNOWN")
        category_sites[cat].append(site)

    categories = sorted(list(category_sites.keys()))
    print(f"📌 Tìm thấy {len(categories)} nhóm sự cố: {categories}")

    baseline_site_names = set()
    no_baseline_site_names = set()

    for idx, cat in enumerate(categories):
        cat_sites = sorted(category_sites[cat], key=lambda s: extract_site_num(s.get("name", "")))
        # 4 nhóm lấy 13 site có baseline, 4 nhóm lấy 12 site có baseline -> Tổng = 100
        quota_has_baseline = 13 if idx % 2 == 0 else 12

        for i, site in enumerate(cat_sites):
            site_name = site["name"]
            if i < quota_has_baseline:
                site["has_baseline"] = True
                if not site.get("baseline_dns"):
                    site["baseline_dns"] = {
                        "a": ["127.0.0.1"],
                        "aaaa": [],
                        "cname": None,
                        "mx": [],
                        "txt": []
                    }
                baseline_site_names.add(site_name)
            else:
                site["has_baseline"] = False
                site["baseline_dns"] = None
                no_baseline_site_names.add(site_name)

        has_in_cat = sum(1 for s in cat_sites if s.get("has_baseline"))
        no_in_cat = sum(1 for s in cat_sites if not s.get("has_baseline"))
        print(f"  • Nhóm {cat:<16}: {has_in_cat} CÓ Baseline | {no_in_cat} KHÔNG CÓ Baseline")

    with open(TARGET_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"\n✅ Đã cập nhật target_websites.json: {len(baseline_site_names)} site CÓ Baseline, {len(no_baseline_site_names)} site KHÔNG CÓ Baseline.")

    # 2. Đồng bộ vào SQLite Database
    if DB_FILE.exists():
        conn = sqlite3.connect(str(DB_FILE))
        conn.execute("PRAGMA journal_mode = WAL;")
        cursor = conn.cursor()

        cursor.execute("SELECT id, name FROM websites;")
        db_sites = cursor.fetchall()

        ensured_active = 0
        removed_count = 0

        for site_id, name in db_sites:
            if name in baseline_site_names:
                # Website cần có baseline
                cursor.execute("SELECT id FROM milestone_baselines WHERE website_id = ? AND is_active = 1;", (site_id,))
                row = cursor.fetchone()
                if not row:
                    cursor.execute("""
                        INSERT INTO milestone_baselines (
                            website_id, website_name, created_at, baseline_dns_json,
                            expected_http_status, note, is_active
                        ) VALUES (?, ?, datetime('now'), ?, 200, 'Mốc chuẩn Managed Service', 1);
                    """, (site_id, name, json.dumps({"a": ["127.0.0.1"], "aaaa": [], "cname": None, "mx": [], "txt": []})))
                ensured_active += 1
            else:
                # Website không có baseline -> Xóa sạch khỏi milestone_baselines
                cursor.execute("DELETE FROM milestone_baselines WHERE website_id = ?;", (site_id,))
                removed_count += 1

        conn.commit()
        conn.close()
        print(f"✅ Đã đồng bộ SQLite Database: {ensured_active} site có Baseline active, {removed_count} site không có Baseline.")

if __name__ == "__main__":
    partition_baselines()

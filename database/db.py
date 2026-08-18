import os
import json
import sqlite3
from typing import Optional

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
DB_PATH = os.path.join(DATA_DIR, "monitoring.db")
CONFIG_PATH = os.path.join(BASE_DIR, "target_websites.json")

def get_db_connection() -> sqlite3.Connection:
    """Tạo kết nối tới cơ sở dữ liệu SQLite với row_factory hỗ trợ truy xuất theo tên cột."""
    os.makedirs(DATA_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn

def init_db() -> None:
    """
    Khởi tạo cơ sở dữ liệu SQLite theo chuẩn RULE_DESIGN_DB.md.
    Tạo các bảng: websites, milestone_baselines, monitoring_logs.
    Tự động nạp dữ liệu mẫu ban đầu từ target_websites.json nếu bảng websites đang trống.
    """
    os.makedirs(DATA_DIR, exist_ok=True)
    conn = get_db_connection()
    cursor = conn.cursor()

    # 1. Bảng websites (Master entity)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS websites (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL UNIQUE,
        url TEXT NOT NULL,
        domain TEXT NOT NULL,
        expected_status INTEGER DEFAULT 200
    );
    """)

    # 2. Bảng milestone_baselines (Quản lý các mốc chuẩn)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS milestone_baselines (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        website_id INTEGER NOT NULL,
        website_name TEXT NOT NULL,
        created_at TEXT NOT NULL,
        baseline_dns_json TEXT NOT NULL,
        expected_http_status INTEGER DEFAULT 200,
        note TEXT,
        is_active BOOLEAN DEFAULT 1,
        FOREIGN KEY (website_id) REFERENCES websites(id) ON DELETE CASCADE
    );
    """)

    # 3. Bảng monitoring_logs (Lịch sử giám sát)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS monitoring_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        website_id INTEGER NOT NULL,
        website_name TEXT NOT NULL,
        timestamp TEXT NOT NULL,
        http_status_code INTEGER,
        http_latency_ms REAL,
        http_is_expected BOOLEAN,
        dns_resolved BOOLEAN,
        dns_latency_ms REAL,
        dns_is_load_balancing BOOLEAN,
        ssl_is_valid BOOLEAN,
        ssl_days_remaining INTEGER,
        ssl_tls_version TEXT,
        full_signals_json TEXT,
        overall_status TEXT,
        FOREIGN KEY (website_id) REFERENCES websites(id) ON DELETE CASCADE
    );
    """)

    # Tạo indexes để tăng tốc truy vấn lịch sử theo website và thời gian
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_logs_website_id ON monitoring_logs(website_id);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_logs_timestamp ON monitoring_logs(timestamp);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_baselines_website_id ON milestone_baselines(website_id);")

    # Seed dữ liệu ban đầu nếu chưa có website nào trong DB
    cursor.execute("SELECT COUNT(*) FROM websites;")
    if cursor.fetchone()[0] == 0 and os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                config_data = json.load(f)
                
            from datetime import datetime, timezone, timedelta
            TZ_VN = timezone(timedelta(hours=7))
            now_iso = datetime.now(TZ_VN).isoformat()
            
            for site in config_data.get("websites", []):
                cursor.execute("""
                    INSERT INTO websites (name, url, domain, expected_status)
                    VALUES (?, ?, ?, ?)
                """, (
                    site["name"],
                    site["url"],
                    site["domain"],
                    site.get("expected_status", 200)
                ))
                website_id = cursor.lastrowid
                
                # Seed baseline ban đầu nếu có
                baseline_dns = site.get("baseline_dns", {})
                cursor.execute("""
                    INSERT INTO milestone_baselines (
                        website_id, website_name, created_at, baseline_dns_json, 
                        expected_http_status, note, is_active
                    ) VALUES (?, ?, ?, ?, ?, ?, 1)
                """, (
                    website_id,
                    site["name"],
                    now_iso,
                    json.dumps(baseline_dns, ensure_ascii=False),
                    site.get("expected_status", 200),
                    "Mốc chuẩn khởi tạo từ cấu hình ban đầu"
                ))
        except Exception as e:
            print(f"Warning: Không thể seed dữ liệu ban đầu: {e}")

    conn.commit()
    conn.close()

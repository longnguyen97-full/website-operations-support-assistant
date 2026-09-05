import os
import json
import sqlite3
from typing import Optional
from datetime import datetime

from config import (
    DATA_DIR,
    DB_PATH,
    TARGET_WEBSITES_FILE,
    TZ_VN,
    DEFAULT_SMTP_SERVER,
    DEFAULT_SMTP_PORT,
    DEFAULT_SENDER_EMAIL,
    DEFAULT_SENDER_PASSWORD,
    DEFAULT_RECIPIENT_EMAILS,
    DEFAULT_USE_TLS,
    DEFAULT_EMAIL_ENABLED,
    DEFAULT_NOTIFY_CRITICAL,
    DEFAULT_NOTIFY_WARNING,
    DEFAULT_NOTIFY_RECOVERY,
    DEFAULT_COOLDOWN_MINUTES,
    DEFAULT_ENABLE_DAILY_REPORT,
    DEFAULT_DAILY_REPORT_TIME,
    DEFAULT_SCHEDULER_INTERVAL_SECONDS,
    DATA_RETENTION_DAYS,
    SSL_EXPIRY_WARNING_DAYS,
    DEFAULT_GEMINI_API_KEY,
    DEFAULT_GEMINI_MODEL,
    DEFAULT_LLM_ENABLED
)

def get_db_connection(timeout: float = 30.0) -> sqlite3.Connection:
    """
    Tạo kết nối tới cơ sở dữ liệu SQLite:
    - row_factory hỗ trợ truy xuất theo tên cột (sqlite3.Row).
    - Chế độ WAL (Write-Ahead Logging) cho phép đọc và ghi đồng thời, triệt tiêu lỗi 'database is locked'.
    - busy_timeout 30s giúp tự động xếp hàng và chờ các giao dịch ghi khi tải cao.
    """
    os.makedirs(DATA_DIR, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH), timeout=timeout)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.execute("PRAGMA journal_mode = WAL;")
    conn.execute("PRAGMA busy_timeout = 30000;")
    conn.execute("PRAGMA synchronous = NORMAL;")
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

    # 4. Bảng system_settings (Cấu hình động: Email, Scheduler, Báo cáo, Lưu trữ & Timeout Probes)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS system_settings (
        id INTEGER PRIMARY KEY CHECK (id = 1),
        -- Cấu hình Email & SMTP (Dynamic)
        smtp_server TEXT DEFAULT 'smtp.gmail.com',
        smtp_port INTEGER DEFAULT 587,
        sender_email TEXT DEFAULT '',
        sender_password TEXT DEFAULT '',
        recipient_emails TEXT DEFAULT '',
        use_tls BOOLEAN DEFAULT 1,
        is_enabled BOOLEAN DEFAULT 0,
        notify_on_critical BOOLEAN DEFAULT 1,
        notify_on_warning BOOLEAN DEFAULT 1,
        notify_on_recovery BOOLEAN DEFAULT 1,
        cooldown_minutes INTEGER DEFAULT 15,
        -- Cấu hình Báo cáo Định kỳ (Dynamic)
        enable_daily_report BOOLEAN DEFAULT 0,
        daily_report_time TEXT DEFAULT '08:00',
        last_report_sent_at TEXT,
        -- Cấu hình Scheduler & Vận hành (Dynamic - Mặc định 4 tiếng = 14400s)
        scheduler_interval_seconds INTEGER DEFAULT 14400,
        data_retention_days INTEGER DEFAULT 30,
        ssl_warning_days INTEGER DEFAULT 14,
        -- Cấu hình Timeout Mạng / Probes (Dynamic)
        http_timeout_seconds REAL DEFAULT 10.0,
        dns_timeout_seconds REAL DEFAULT 5.0,
        ssl_timeout_seconds REAL DEFAULT 10.0,
        -- Cấu hình Chế độ Giám sát (Mặc định: AGENTIC)
        monitoring_mode TEXT DEFAULT 'AGENTIC',
        latency_threshold_ms REAL DEFAULT 2000.0,
        -- Cấu hình AI & LLM Reasoning (Gemini)
        gemini_api_key TEXT DEFAULT '',
        gemini_model TEXT DEFAULT 'gemini-1.5-flash',
        llm_enabled BOOLEAN DEFAULT 0,
        updated_at TEXT
    );
    """)

    # Tự động đồng bộ và di chuyển cột mới nếu nâng cấp từ email_settings cũ
    cursor.execute("CREATE TABLE IF NOT EXISTS email_settings AS SELECT * FROM system_settings WHERE 0;")
    for col, col_type in [
        ("enable_daily_report", "BOOLEAN DEFAULT 0"),
        ("daily_report_time", "TEXT DEFAULT '08:00'"),
        ("last_report_sent_at", "TEXT"),
        ("scheduler_interval_seconds", "INTEGER DEFAULT 14400"),
        ("data_retention_days", "INTEGER DEFAULT 30"),
        ("ssl_warning_days", "INTEGER DEFAULT 14"),
        ("http_timeout_seconds", "REAL DEFAULT 10.0"),
        ("dns_timeout_seconds", "REAL DEFAULT 5.0"),
        ("ssl_timeout_seconds", "REAL DEFAULT 10.0"),
        ("monitoring_mode", "TEXT DEFAULT 'AGENTIC'"),
        ("latency_threshold_ms", "REAL DEFAULT 2000.0"),
        ("gemini_api_key", "TEXT DEFAULT ''"),
        ("gemini_model", "TEXT DEFAULT 'gemini-1.5-flash'"),
        ("llm_enabled", "BOOLEAN DEFAULT 0")
    ]:
        try:
            cursor.execute(f"ALTER TABLE system_settings ADD COLUMN {col} {col_type};")
        except sqlite3.OperationalError:
            pass

    # Tạo bản ghi system_settings mặc định nếu chưa tồn tại
    cursor.execute("SELECT COUNT(*) FROM system_settings WHERE id = 1;")
    if cursor.fetchone()[0] == 0:
        cursor.execute("""
            INSERT INTO system_settings (
                id, smtp_server, smtp_port, sender_email, sender_password,
                recipient_emails, use_tls, is_enabled, 
                notify_on_critical, notify_on_warning, notify_on_recovery, 
                cooldown_minutes, enable_daily_report, daily_report_time,
                scheduler_interval_seconds, data_retention_days, ssl_warning_days,
                http_timeout_seconds, dns_timeout_seconds, ssl_timeout_seconds,
                gemini_api_key, gemini_model, llm_enabled
            ) VALUES (1, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
        """, (
            DEFAULT_SMTP_SERVER,
            DEFAULT_SMTP_PORT,
            DEFAULT_SENDER_EMAIL,
            DEFAULT_SENDER_PASSWORD,
            DEFAULT_RECIPIENT_EMAILS,
            1 if DEFAULT_USE_TLS else 0,
            1 if DEFAULT_EMAIL_ENABLED else 0,
            1 if DEFAULT_NOTIFY_CRITICAL else 0,
            1 if DEFAULT_NOTIFY_WARNING else 0,
            1 if DEFAULT_NOTIFY_RECOVERY else 0,
            DEFAULT_COOLDOWN_MINUTES,
            1 if DEFAULT_ENABLE_DAILY_REPORT else 0,
            DEFAULT_DAILY_REPORT_TIME,
            DEFAULT_SCHEDULER_INTERVAL_SECONDS,
            DATA_RETENTION_DAYS,
            SSL_EXPIRY_WARNING_DAYS,
            10.0,
            5.0,
            10.0,
            DEFAULT_GEMINI_API_KEY,
            DEFAULT_GEMINI_MODEL,
            1 if DEFAULT_LLM_ENABLED else 0
        ))

    # Tạo indexes để tăng tốc truy vấn lịch sử theo website và thời gian
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_logs_website_id ON monitoring_logs(website_id);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_logs_timestamp ON monitoring_logs(timestamp);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_baselines_website_id ON milestone_baselines(website_id);")

    # Seed dữ liệu ban đầu nếu chưa có website nào trong DB
    cursor.execute("SELECT COUNT(*) FROM websites;")
    if cursor.fetchone()[0] == 0 and os.path.exists(str(TARGET_WEBSITES_FILE)):
        try:
            with open(str(TARGET_WEBSITES_FILE), "r", encoding="utf-8") as f:
                config_data = json.load(f)
                
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
                
                # Seed baseline ban đầu nếu website được cấu hình có Baseline (Managed Site)
                if site.get("has_baseline", True) and site.get("baseline_dns"):
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
                        "Mốc chuẩn khởi tạo từ cấu hình ban đầu (Managed Site)"
                    ))
        except Exception as e:
            print(f"Warning: Không thể seed dữ liệu ban đầu: {e}")

    conn.commit()
    conn.close()

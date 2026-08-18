import json
import sqlite3
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from database.db import get_db_connection
from config import (
    TZ_VN,
    SSL_EXPIRY_WARNING_DAYS,
    DATA_RETENTION_DAYS,
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
    DEFAULT_SCHEDULER_INTERVAL_SECONDS
)

def calculate_overall_status(http_res: dict, dns_res: dict, ssl_res: dict) -> str:
    """Xác định trạng thái tổng thể: HEALTHY, WARNING, hoặc CRITICAL."""
    # Nếu có lỗi nghiêm trọng (HTTP không kết nối, DNS thất bại, hoặc SSL không hợp lệ)
    if (not http_res.get("is_expected_status") and not http_res.get("is_success")) or \
       not dns_res.get("resolved") or \
       not ssl_res.get("is_valid"):
        return "CRITICAL"
    
    # Nếu chứng chỉ sắp hết hạn trong ngưỡng cảnh báo hoặc mã HTTP không đúng như mong đợi (nhưng vẫn có response)
    if (ssl_res.get("days_remaining", 0) <= SSL_EXPIRY_WARNING_DAYS) or \
       (not http_res.get("is_expected_status")):
        return "WARNING"
        
    return "HEALTHY"

# ==================== 1. QUẢN LÝ WEBSITE ====================

def get_all_websites() -> List[Dict[str, Any]]:
    """Lấy danh sách tất cả website được cấu hình trong CSDL."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, name, url, domain, expected_status FROM websites ORDER BY id ASC;")
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def get_website_by_id(website_id: int) -> Optional[Dict[str, Any]]:
    """Lấy thông tin website theo ID."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, name, url, domain, expected_status FROM websites WHERE id = ?;", (website_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

def get_website_by_name(name: str) -> Optional[Dict[str, Any]]:
    """Lấy thông tin website theo tên định danh."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, name, url, domain, expected_status FROM websites WHERE name = ?;", (name,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

def add_or_update_website(name: str, url: str, domain: str, expected_status: int = 200) -> int:
    """Thêm mới hoặc cập nhật thông tin website."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO websites (name, url, domain, expected_status)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(name) DO UPDATE SET
            url = excluded.url,
            domain = excluded.domain,
            expected_status = excluded.expected_status;
    """, (name, url, domain, expected_status))
    website_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return website_id

def delete_website(website_id: int) -> bool:
    """Xóa website và các dữ liệu liên quan (Cascade)."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM websites WHERE id = ?;", (website_id,))
    conn.commit()
    deleted = cursor.rowcount > 0
    conn.close()
    return deleted

# ==================== 2. QUẢN LÝ LỊCH SỬ GIÁM SÁT (MONITORING LOGS) ====================

def save_monitoring_log(
    website_id: int,
    website_name: str,
    http_res: dict,
    dns_res: dict,
    ssl_res: dict,
    timestamp: Optional[str] = None
) -> int:
    """Lưu trữ một bản ghi kết quả kiểm tra giám sát vào bảng monitoring_logs."""
    if not timestamp:
        timestamp = datetime.now(TZ_VN).isoformat()

    overall_status = calculate_overall_status(http_res, dns_res, ssl_res)
    
    full_signals = {
        "http": http_res,
        "dns": dns_res,
        "ssl": ssl_res
    }

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO monitoring_logs (
            website_id, website_name, timestamp,
            http_status_code, http_latency_ms, http_is_expected,
            dns_resolved, dns_latency_ms, dns_is_load_balancing,
            ssl_is_valid, ssl_days_remaining, ssl_tls_version,
            full_signals_json, overall_status
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        website_id,
        website_name,
        timestamp,
        http_res.get("status_code"),
        http_res.get("response_time_ms"),
        1 if http_res.get("is_expected_status") else 0,
        1 if dns_res.get("resolved") else 0,
        dns_res.get("resolution_time_ms"),
        1 if dns_res.get("is_load_balancing_suspected") else 0,
        1 if ssl_res.get("is_valid") else 0,
        ssl_res.get("days_remaining", 0),
        ssl_res.get("tls_version"),
        json.dumps(full_signals, ensure_ascii=False),
        overall_status
    ))
    log_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return log_id

def get_monitoring_logs(website_id: Optional[int] = None, limit: int = 50) -> List[Dict[str, Any]]:
    """Truy vấn danh sách lịch sử kiểm tra gần nhất."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    if website_id is not None:
        cursor.execute("""
            SELECT * FROM monitoring_logs
            WHERE website_id = ?
            ORDER BY id DESC
            LIMIT ?;
        """, (website_id, limit))
    else:
        cursor.execute("""
            SELECT * FROM monitoring_logs
            ORDER BY id DESC
            LIMIT ?;
        """, (limit,))
        
    rows = cursor.fetchall()
    conn.close()
    
    result = []
    for r in rows:
        item = dict(r)
        if item.get("full_signals_json"):
            try:
                item["full_signals"] = json.loads(item["full_signals_json"])
            except Exception:
                item["full_signals"] = {}
        result.append(item)
    return result

def purge_old_logs(days_to_keep: int = 30) -> int:
    """Dọn dẹp các bản ghi log quá cũ theo chính sách Data Retention trong RULE_DESIGN_DB.md."""
    cutoff_time = (datetime.now(TZ_VN) - timedelta(days=days_to_keep)).isoformat()
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM monitoring_logs WHERE timestamp < ?;", (cutoff_time,))
    deleted_count = cursor.rowcount
    conn.commit()
    conn.close()
    return deleted_count

# ==================== 3. QUẢN LÝ MỐC CHUẨN (MILESTONE BASELINES) ====================

def save_milestone_baseline(
    website_id: int,
    website_name: str,
    baseline_dns: dict,
    expected_http_status: int = 200,
    note: str = "",
    set_active: bool = True
) -> int:
    """Tạo mới một mốc chuẩn. Nếu set_active=True, tự động tắt cờ is_active của các mốc cũ."""
    created_at = datetime.now(TZ_VN).isoformat()
    conn = get_db_connection()
    cursor = conn.cursor()
    
    if set_active:
        cursor.execute("""
            UPDATE milestone_baselines
            SET is_active = 0
            WHERE website_id = ?;
        """, (website_id,))
        
    cursor.execute("""
        INSERT INTO milestone_baselines (
            website_id, website_name, created_at, baseline_dns_json,
            expected_http_status, note, is_active
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (
        website_id,
        website_name,
        created_at,
        json.dumps(baseline_dns, ensure_ascii=False),
        expected_http_status,
        note,
        1 if set_active else 0
    ))
    milestone_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return milestone_id

def get_active_baseline(website_id: int) -> Optional[Dict[str, Any]]:
    """Lấy mốc chuẩn đang có hiệu lực (is_active = 1) của website."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT * FROM milestone_baselines
        WHERE website_id = ? AND is_active = 1
        ORDER BY id DESC
        LIMIT 1;
    """, (website_id,))
    row = cursor.fetchone()
    conn.close()
    
    if row:
        res = dict(row)
        try:
            res["baseline_dns"] = json.loads(res["baseline_dns_json"])
        except Exception:
            res["baseline_dns"] = {}
        return res
    return None

def get_all_milestones(website_id: Optional[int] = None) -> List[Dict[str, Any]]:
    """Lấy danh sách tất cả các mốc chuẩn đã lưu."""
    conn = get_db_connection()
    cursor = conn.cursor()
    if website_id is not None:
        cursor.execute("""
            SELECT * FROM milestone_baselines
            WHERE website_id = ?
            ORDER BY id DESC;
        """, (website_id,))
    else:
        cursor.execute("""
            SELECT * FROM milestone_baselines
            ORDER BY id DESC;
        """)
    rows = cursor.fetchall()
    conn.close()
    
    result = []
    for r in rows:
        item = dict(r)
        try:
            item["baseline_dns"] = json.loads(item["baseline_dns_json"])
        except Exception:
            item["baseline_dns"] = {}
        result.append(item)
    return result

def set_active_milestone(milestone_id: int, website_id: int) -> bool:
    """Chuyển đổi kích hoạt mốc chuẩn hiệu lực cho website."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE milestone_baselines SET is_active = 0 WHERE website_id = ?;", (website_id,))
    cursor.execute("UPDATE milestone_baselines SET is_active = 1 WHERE id = ? AND website_id = ?;", (milestone_id, website_id))
    conn.commit()
    success = cursor.rowcount > 0
    conn.close()
    return success

# ==================== 4. QUẢN LÝ CẤU HÌNH HỆ THỐNG (SYSTEM & EMAIL SETTINGS) ====================

def get_system_settings() -> Dict[str, Any]:
    """Lấy thông tin cấu hình động từ CSDL (tự động Fallback sang .env/config.py nếu trường trong DB rỗng)."""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT * FROM system_settings WHERE id = 1;")
        row = cursor.fetchone()
    except Exception:
        row = None
    conn.close()
    
    settings = dict(row) if row else {}
    
    # Áp dụng cơ chế Fallback thông minh: nếu trường trong DB rỗng thì lấy từ .env/config.py
    return {
        "id": 1,
        "smtp_server": settings.get("smtp_server") or DEFAULT_SMTP_SERVER,
        "smtp_port": settings.get("smtp_port") or DEFAULT_SMTP_PORT,
        "sender_email": settings.get("sender_email") or DEFAULT_SENDER_EMAIL,
        "sender_password": settings.get("sender_password") or DEFAULT_SENDER_PASSWORD,
        "recipient_emails": settings.get("recipient_emails") or DEFAULT_RECIPIENT_EMAILS,
        "use_tls": settings.get("use_tls", 1 if DEFAULT_USE_TLS else 0),
        "is_enabled": settings.get("is_enabled", 1 if DEFAULT_EMAIL_ENABLED else 0),
        "notify_on_critical": settings.get("notify_on_critical", 1 if DEFAULT_NOTIFY_CRITICAL else 0),
        "notify_on_warning": settings.get("notify_on_warning", 1 if DEFAULT_NOTIFY_WARNING else 0),
        "notify_on_recovery": settings.get("notify_on_recovery", 1 if DEFAULT_NOTIFY_RECOVERY else 0),
        "cooldown_minutes": settings.get("cooldown_minutes") or DEFAULT_COOLDOWN_MINUTES,
        "enable_daily_report": settings.get("enable_daily_report", 1 if DEFAULT_ENABLE_DAILY_REPORT else 0),
        "daily_report_time": settings.get("daily_report_time") or DEFAULT_DAILY_REPORT_TIME,
        "scheduler_interval_seconds": settings.get("scheduler_interval_seconds") or DEFAULT_SCHEDULER_INTERVAL_SECONDS,
        "data_retention_days": settings.get("data_retention_days") or DATA_RETENTION_DAYS,
        "ssl_warning_days": settings.get("ssl_warning_days") or SSL_EXPIRY_WARNING_DAYS,
        "last_report_sent_at": settings.get("last_report_sent_at")
    }

get_email_settings = get_system_settings

def sync_settings_from_env() -> Dict[str, Any]:
    """Nạp và đồng bộ lại toàn bộ thông số từ file .env / config.py vào CSDL SQLite."""
    import importlib
    import config
    from dotenv import load_dotenv
    if (config.BASE_DIR / ".env").exists():
        load_dotenv(dotenv_path=config.BASE_DIR / ".env", override=True)
    importlib.reload(config)

    env_settings = {
        "smtp_server": config.DEFAULT_SMTP_SERVER,
        "smtp_port": config.DEFAULT_SMTP_PORT,
        "sender_email": config.DEFAULT_SENDER_EMAIL,
        "sender_password": config.DEFAULT_SENDER_PASSWORD,
        "recipient_emails": config.DEFAULT_RECIPIENT_EMAILS,
        "use_tls": config.DEFAULT_USE_TLS,
        "is_enabled": config.DEFAULT_EMAIL_ENABLED,
        "notify_on_critical": config.DEFAULT_NOTIFY_CRITICAL,
        "notify_on_warning": config.DEFAULT_NOTIFY_WARNING,
        "notify_on_recovery": config.DEFAULT_NOTIFY_RECOVERY,
        "cooldown_minutes": config.DEFAULT_COOLDOWN_MINUTES,
        "enable_daily_report": config.DEFAULT_ENABLE_DAILY_REPORT,
        "daily_report_time": config.DEFAULT_DAILY_REPORT_TIME,
        "scheduler_interval_seconds": config.DEFAULT_SCHEDULER_INTERVAL_SECONDS,
        "data_retention_days": config.DATA_RETENTION_DAYS,
        "ssl_warning_days": config.SSL_EXPIRY_WARNING_DAYS
    }
    update_system_settings(env_settings)
    return env_settings

def update_system_settings(settings: Dict[str, Any]) -> bool:
    """Cập nhật thông tin cấu hình động hệ thống vào CSDL."""
    updated_at = datetime.now(TZ_VN).isoformat()
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO system_settings (
            id, smtp_server, smtp_port, sender_email, sender_password,
            recipient_emails, use_tls, is_enabled, notify_on_critical,
            notify_on_warning, notify_on_recovery, cooldown_minutes,
            enable_daily_report, daily_report_time,
            scheduler_interval_seconds, data_retention_days, ssl_warning_days,
            updated_at
        ) VALUES (1, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            smtp_server = excluded.smtp_server,
            smtp_port = excluded.smtp_port,
            sender_email = excluded.sender_email,
            sender_password = excluded.sender_password,
            recipient_emails = excluded.recipient_emails,
            use_tls = excluded.use_tls,
            is_enabled = excluded.is_enabled,
            notify_on_critical = excluded.notify_on_critical,
            notify_on_warning = excluded.notify_on_warning,
            notify_on_recovery = excluded.notify_on_recovery,
            cooldown_minutes = excluded.cooldown_minutes,
            enable_daily_report = excluded.enable_daily_report,
            daily_report_time = excluded.daily_report_time,
            scheduler_interval_seconds = excluded.scheduler_interval_seconds,
            data_retention_days = excluded.data_retention_days,
            ssl_warning_days = excluded.ssl_warning_days,
            updated_at = excluded.updated_at;
    """, (
        settings.get("smtp_server", DEFAULT_SMTP_SERVER),
        int(settings.get("smtp_port", DEFAULT_SMTP_PORT)),
        str(settings.get("sender_email", DEFAULT_SENDER_EMAIL)).strip(),
        str(settings.get("sender_password", DEFAULT_SENDER_PASSWORD)).strip(),
        str(settings.get("recipient_emails", DEFAULT_RECIPIENT_EMAILS)).strip(),
        1 if settings.get("use_tls", DEFAULT_USE_TLS) else 0,
        1 if settings.get("is_enabled", DEFAULT_EMAIL_ENABLED) else 0,
        1 if settings.get("notify_on_critical", DEFAULT_NOTIFY_CRITICAL) else 0,
        1 if settings.get("notify_on_warning", DEFAULT_NOTIFY_WARNING) else 0,
        1 if settings.get("notify_on_recovery", DEFAULT_NOTIFY_RECOVERY) else 0,
        int(settings.get("cooldown_minutes", DEFAULT_COOLDOWN_MINUTES)),
        1 if settings.get("enable_daily_report", DEFAULT_ENABLE_DAILY_REPORT) else 0,
        str(settings.get("daily_report_time", DEFAULT_DAILY_REPORT_TIME)).strip(),
        int(settings.get("scheduler_interval_seconds", DEFAULT_SCHEDULER_INTERVAL_SECONDS)),
        int(settings.get("data_retention_days", DATA_RETENTION_DAYS)),
        int(settings.get("ssl_warning_days", SSL_EXPIRY_WARNING_DAYS)),
        updated_at
    ))
    conn.commit()
    success = cursor.rowcount > 0
    conn.close()
    return success

update_email_settings = update_system_settings

# ==================== 5. BÁO CÁO ĐỊNH KỲ (PERIODIC HEALTH REPORT) ====================

def generate_periodic_report_data(hours: int = 24) -> Dict[str, Any]:
    """Tổng hợp dữ liệu giám sát trong `hours` giờ qua để tạo báo cáo định kỳ."""
    cutoff_time = (datetime.now(TZ_VN) - timedelta(hours=hours)).isoformat()
    now_str = datetime.now(TZ_VN).strftime("%Y-%m-%d %H:%M:%S")

    conn = get_db_connection()
    cursor = conn.cursor()

    # 1. Danh sách website
    websites = get_all_websites()
    
    # 2. Truy vấn logs trong khoảng thời gian
    cursor.execute("""
        SELECT * FROM monitoring_logs
        WHERE timestamp >= ?
        ORDER BY id DESC;
    """, (cutoff_time,))
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()

    total_scans = len(rows)
    healthy_scans = len([r for r in rows if r.get("overall_status") == "HEALTHY"])
    warning_scans = len([r for r in rows if r.get("overall_status") == "WARNING"])
    critical_scans = len([r for r in rows if r.get("overall_status") == "CRITICAL"])
    overall_health_rate = round((healthy_scans / total_scans) * 100, 1) if total_scans > 0 else 100.0

    # 3. Phân tích theo từng website
    site_summaries = []
    for site in websites:
        site_rows = [r for r in rows if r.get("website_id") == site["id"]]
        site_total = len(site_rows)
        site_healthy = len([r for r in site_rows if r.get("overall_status") == "HEALTHY"])
        site_critical = len([r for r in site_rows if r.get("overall_status") == "CRITICAL"])
        site_warning = len([r for r in site_rows if r.get("overall_status") == "WARNING"])
        
        avg_http = round(sum([r.get("http_latency_ms") or 0 for r in site_rows]) / site_total, 2) if site_total > 0 else 0.0
        avg_dns = round(sum([r.get("dns_latency_ms") or 0 for r in site_rows]) / site_total, 2) if site_total > 0 else 0.0
        site_health_rate = round((site_healthy / site_total) * 100, 1) if site_total > 0 else 100.0
        
        # Lấy thông tin probe mới nhất
        latest_row = site_rows[0] if site_rows else None
        current_status = latest_row.get("overall_status") if latest_row else "UNKNOWN"
        ssl_days = latest_row.get("ssl_days_remaining") if latest_row else 0
        ssl_valid = bool(latest_row.get("ssl_is_valid")) if latest_row else True
        http_code = latest_row.get("http_status_code") if latest_row else None
        
        site_summaries.append({
            "website_id": site["id"],
            "name": site["name"],
            "url": site["url"],
            "domain": site["domain"],
            "current_status": current_status,
            "total_scans": site_total,
            "health_rate": site_health_rate,
            "avg_http_latency_ms": avg_http,
            "avg_dns_latency_ms": avg_dns,
            "ssl_days_remaining": ssl_days,
            "ssl_is_valid": ssl_valid,
            "latest_http_code": http_code,
            "critical_count": site_critical,
            "warning_count": site_warning
        })

    # 4. Danh sách các sự cố trong khoảng thời gian (Top 10)
    incidents = [
        {
            "timestamp": r["timestamp"],
            "website_name": r["website_name"],
            "status": r["overall_status"],
            "http_code": r["http_status_code"],
            "dns_resolved": r["dns_resolved"],
            "ssl_valid": r["ssl_is_valid"],
            "ssl_days": r["ssl_days_remaining"]
        }
        for r in rows if r.get("overall_status") in ["CRITICAL", "WARNING"]
    ][:10]

    return {
        "report_generated_at": now_str,
        "period_hours": hours,
        "total_websites": len(websites),
        "total_scans": total_scans,
        "overall_health_rate": overall_health_rate,
        "healthy_scans": healthy_scans,
        "warning_scans": warning_scans,
        "critical_scans": critical_scans,
        "sites": site_summaries,
        "incidents": incidents
    }

def record_report_sent_time():
    """Ghi nhận thời điểm gửi báo cáo gần nhất vào CSDL."""
    now_iso = datetime.now(TZ_VN).isoformat()
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE system_settings SET last_report_sent_at = ? WHERE id = 1;", (now_iso,))
    conn.commit()
    conn.close()


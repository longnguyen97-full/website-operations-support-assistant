import os
import time
import json
import sqlite3
from pathlib import Path
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
    DEFAULT_SCHEDULER_INTERVAL_SECONDS,
    DEFAULT_GEMINI_API_KEY,
    DEFAULT_GEMINI_MODEL,
    DEFAULT_LLM_ENABLED
)

def calculate_overall_status(
    http_res: dict,
    dns_res: dict,
    ssl_res: dict,
    dom_res: Optional[dict] = None,
    visual_res: Optional[dict] = None
) -> str:
    """Xác định trạng thái tổng thể: HEALTHY, WARNING, hoặc CRITICAL."""
    # 1. Nếu có lỗi nghiêm trọng (HTTP không kết nối / 5xx, DNS thất bại, hoặc SSL không hợp lệ)
    if (not http_res.get("is_expected_status") and not http_res.get("is_success")) or \
       not dns_res.get("resolved") or \
       not ssl_res.get("is_valid"):
        return "CRITICAL"
    
    # 2. Nếu cấu trúc DOM bị lỗi nghiêm trọng (Missing DOM / Blank Page)
    if dom_res and not dom_res.get("is_structure_valid", True):
        missing = dom_res.get("missing_critical_elements", [])
        if "Body Content" in missing:
            return "CRITICAL"
        return "WARNING"

    # 3. Nếu phát hiện biến dạng giao diện (Visual Regression)
    if visual_res and visual_res.get("is_regression_detected"):
        diff_pct = visual_res.get("diff_percentage", 0.0)
        return "CRITICAL" if diff_pct >= 10.0 else "WARNING"

    # 4. Nếu chứng chỉ sắp hết hạn trong ngưỡng cảnh báo hoặc mã HTTP không đúng như mong đợi (nhưng vẫn có response)
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

def sync_websites_from_json_file(file_path: Optional[str] = None, replace_all: bool = True) -> Dict[str, Any]:
    """
    Đồng bộ và nạp toàn bộ danh sách website từ tệp JSON cấu hình (mặc định target_websites.json) vào CSDL SQLite.
    Nếu replace_all=True: Loại bỏ các website cũ không còn nằm trong file cấu hình để chỉ lưu giữ dataset_200_websites.
    Tự động cập nhật hoặc thêm mới và khởi tạo mốc chuẩn baseline tương ứng.
    """
    from config import TARGET_WEBSITES_FILE
    target_path = file_path or str(TARGET_WEBSITES_FILE)
    
    if not os.path.exists(target_path):
        return {"success": False, "count": 0, "message": f"Không tìm thấy file cấu hình: {target_path}"}
        
    try:
        with open(target_path, "r", encoding="utf-8") as f:
            config_data = json.load(f)
            
        websites_list = config_data.get("websites", [])
        if not websites_list:
            return {"success": False, "count": 0, "message": "File JSON không chứa danh sách 'websites'."}
            
        conn = get_db_connection()
        cursor = conn.cursor()
        now_iso = datetime.now(TZ_VN).isoformat()

        if replace_all:
            # Thu thập danh sách tên website mới
            new_names = {site.get("name") for site in websites_list if site.get("name")}
            # Xóa các website cũ không nằm trong danh sách mới
            cursor.execute("SELECT id, name FROM websites;")
            existing_rows = cursor.fetchall()
            for row in existing_rows:
                if row["name"] not in new_names:
                    cursor.execute("DELETE FROM websites WHERE id = ?;", (row["id"],))

        synced_count = 0
        for site in websites_list:
            name = site.get("name")
            url = site.get("url")
            domain = site.get("domain")
            expected_status = site.get("expected_status", 200)
            
            if not (name and url and domain):
                continue
                
            cursor.execute("""
                INSERT INTO websites (name, url, domain, expected_status)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(name) DO UPDATE SET
                    url = excluded.url,
                    domain = excluded.domain,
                    expected_status = excluded.expected_status;
            """, (name, url, domain, expected_status))
            
            # Lấy website_id vừa insert/update
            cursor.execute("SELECT id FROM websites WHERE name = ?;", (name,))
            row = cursor.fetchone()
            if row:
                site_id = row[0]
                baseline_dns = site.get("baseline_dns", {})
                
                # Kiểm tra xem đã có baseline chưa, nếu chưa có thì tạo
                cursor.execute("SELECT COUNT(*) FROM milestone_baselines WHERE website_id = ?;", (site_id,))
                if cursor.fetchone()[0] == 0:
                    cursor.execute("""
                        INSERT INTO milestone_baselines (
                            website_id, website_name, created_at, baseline_dns_json, 
                            expected_http_status, note, is_active
                        ) VALUES (?, ?, ?, ?, ?, ?, 1)
                    """, (
                        site_id,
                        name,
                        now_iso,
                        json.dumps(baseline_dns, ensure_ascii=False),
                        expected_status,
                        "Mốc chuẩn khởi tạo tự động từ target_websites.json"
                    ))
            synced_count += 1
            
        conn.commit()
        conn.close()
        return {
            "success": True, 
            "count": synced_count, 
            "message": f"Đã đồng bộ thành công {synced_count} website từ target_websites.json vào CSDL SQLite!"
        }
    except Exception as e:
        return {"success": False, "count": 0, "message": f"Lỗi trong quá trình đồng bộ website: {e}"}


# ==================== 2. QUẢN LÝ LỊCH SỬ GIÁM SÁT (MONITORING LOGS) ====================

def save_monitoring_log(
    website_id: int,
    website_name: str,
    http_res: dict,
    dns_res: dict,
    ssl_res: dict,
    timestamp: Optional[str] = None,
    dom_res: Optional[dict] = None,
    visual_res: Optional[dict] = None,
    agent_res: Optional[dict] = None,
    overall_status: Optional[str] = None
) -> int:
    """Lưu trữ một bản ghi kết quả kiểm tra giám sát vào bảng monitoring_logs."""
    if not timestamp:
        timestamp = datetime.now(TZ_VN).isoformat()

    if overall_status is None:
        overall_status = calculate_overall_status(http_res, dns_res, ssl_res, dom_res=dom_res, visual_res=visual_res)
    
    full_signals = {
        "http": http_res,
        "dns": dns_res,
        "ssl": ssl_res
    }
    if dom_res:
        full_signals["dom"] = dom_res
    if visual_res:
        full_signals["visual"] = visual_res
    if agent_res:
        full_signals["agent"] = {
            "incident_type": agent_res.get("correlation", {}).get("incident_type"),
            "severity": agent_res.get("overall_severity"),
            "root_cause": agent_res.get("correlation", {}).get("root_cause_summary"),
            "title": agent_res.get("rca_analysis", {}).get("incident_title")
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

def get_website_latency_history(website_id: int, limit: int = 50) -> List[float]:
    """Lấy chuỗi độ trễ thời gian (HTTP latency ms) gần nhất của website phục vụ phân tích thống kê."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT http_latency_ms FROM monitoring_logs
        WHERE website_id = ? AND http_latency_ms IS NOT NULL AND http_latency_ms > 0
        ORDER BY id DESC
        LIMIT ?;
    """, (website_id, limit))
    rows = cursor.fetchall()
    conn.close()
    # Trả về theo thứ tự thời gian tăng dần (cũ -> mới)
    latencies = [float(r["http_latency_ms"]) for r in rows if r["http_latency_ms"] is not None]
    latencies.reverse()
    return latencies

def purge_old_artifacts(days_to_keep: int = 30) -> Dict[str, Any]:
    """
    Dọn dẹp rò rỉ dung lượng đĩa: Xóa các file ảnh chụp màn hình và visual diffs cũ
    vượt quá số ngày quy định, bảo toàn các file *_latest.png và baseline chuẩn.
    """
    from config import DATA_DIR
    cutoff_ts = time.time() - (days_to_keep * 86400)
    screenshots_dir = Path(DATA_DIR) / "screenshots"
    diffs_dir = Path(DATA_DIR) / "visual_diffs"
    
    deleted_files = 0
    freed_bytes = 0
    
    for folder in [screenshots_dir, diffs_dir]:
        if folder.exists():
            for p in folder.glob("*.png"):
                if p.name.endswith("_latest.png"):
                    continue
                try:
                    st_val = p.stat()
                    if st_val.st_mtime < cutoff_ts:
                        freed_bytes += st_val.st_size
                        p.unlink(missing_ok=True)
                        deleted_files += 1
                except Exception:
                    pass

    return {
        "deleted_files": deleted_files,
        "freed_mb": round(freed_bytes / (1024 * 1024), 2)
    }

def purge_old_logs(days_to_keep: int = 30) -> int:
    """Dọn dẹp các bản ghi log và file artifacts quá cũ theo chính sách Data Retention."""
    cutoff_time = (datetime.now(TZ_VN) - timedelta(days=days_to_keep)).isoformat()
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM monitoring_logs WHERE timestamp < ?;", (cutoff_time,))
    deleted_count = cursor.rowcount
    try:
        cursor.execute("DELETE FROM system_telemetry_logs WHERE timestamp < ?;", (cutoff_time,))
    except Exception:
        pass
    conn.commit()
    conn.close()
    
    # Tự động dọn dẹp file ảnh artifacts cũ tránh phình đĩa
    purge_old_artifacts(days_to_keep=days_to_keep)
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
        "scheduler_enabled": settings.get("scheduler_enabled", 1),
        "data_retention_days": settings.get("data_retention_days") or DATA_RETENTION_DAYS,
        "ssl_warning_days": settings.get("ssl_warning_days") or SSL_EXPIRY_WARNING_DAYS,
        "http_timeout_seconds": settings.get("http_timeout_seconds") or config.HTTP_TIMEOUT_SECONDS,
        "dns_timeout_seconds": settings.get("dns_timeout_seconds") or config.DNS_TIMEOUT_SECONDS,
        "ssl_timeout_seconds": settings.get("ssl_timeout_seconds") or config.SSL_TIMEOUT_SECONDS,
        "monitoring_mode": settings.get("monitoring_mode") or "AGENTIC",
        "latency_threshold_ms": float(settings.get("latency_threshold_ms") or 2000.0),
        "gemini_api_key": settings.get("gemini_api_key") if settings.get("gemini_api_key") is not None else DEFAULT_GEMINI_API_KEY,
        "gemini_model": settings.get("gemini_model") or DEFAULT_GEMINI_MODEL,
        "llm_enabled": settings.get("llm_enabled", 1 if DEFAULT_LLM_ENABLED else 0),
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
        "ssl_warning_days": config.SSL_EXPIRY_WARNING_DAYS,
        "http_timeout_seconds": config.HTTP_TIMEOUT_SECONDS,
        "dns_timeout_seconds": config.DNS_TIMEOUT_SECONDS,
        "ssl_timeout_seconds": config.SSL_TIMEOUT_SECONDS,
        "monitoring_mode": "AGENTIC",
        "latency_threshold_ms": 2000.0,
        "gemini_api_key": config.DEFAULT_GEMINI_API_KEY,
        "gemini_model": config.DEFAULT_GEMINI_MODEL,
        "llm_enabled": config.DEFAULT_LLM_ENABLED
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
            scheduler_interval_seconds, scheduler_enabled, data_retention_days, ssl_warning_days,
            http_timeout_seconds, dns_timeout_seconds, ssl_timeout_seconds,
            monitoring_mode, latency_threshold_ms,
            gemini_api_key, gemini_model, llm_enabled,
            updated_at
        ) VALUES (1, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
            scheduler_enabled = excluded.scheduler_enabled,
            data_retention_days = excluded.data_retention_days,
            ssl_warning_days = excluded.ssl_warning_days,
            http_timeout_seconds = excluded.http_timeout_seconds,
            dns_timeout_seconds = excluded.dns_timeout_seconds,
            ssl_timeout_seconds = excluded.ssl_timeout_seconds,
            monitoring_mode = excluded.monitoring_mode,
            latency_threshold_ms = excluded.latency_threshold_ms,
            gemini_api_key = excluded.gemini_api_key,
            gemini_model = excluded.gemini_model,
            llm_enabled = excluded.llm_enabled,
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
        1 if settings.get("scheduler_enabled", 1) else 0,
        int(settings.get("data_retention_days", DATA_RETENTION_DAYS)),
        int(settings.get("ssl_warning_days", SSL_EXPIRY_WARNING_DAYS)),
        float(settings.get("http_timeout_seconds", 10.0)),
        float(settings.get("dns_timeout_seconds", 5.0)),
        float(settings.get("ssl_timeout_seconds", 10.0)),
        str(settings.get("monitoring_mode", "AGENTIC")),
        float(settings.get("latency_threshold_ms", 2000.0)),
        str(settings.get("gemini_api_key", DEFAULT_GEMINI_API_KEY)).strip(),
        str(settings.get("gemini_model", DEFAULT_GEMINI_MODEL)).strip(),
        1 if settings.get("llm_enabled", DEFAULT_LLM_ENABLED) else 0,
        updated_at
    ))
    conn.commit()
    success = cursor.rowcount > 0
    conn.close()
    return success

def update_scheduler_settings(interval_seconds: Optional[int] = None, is_enabled: Optional[bool] = None) -> bool:
    """Cập nhật riêng lẻ cấu hình chu kỳ và trạng thái bộ lập lịch vào CSDL."""
    conn = get_db_connection()
    cursor = conn.cursor()
    updated_at = datetime.now(TZ_VN).isoformat()
    if interval_seconds is not None and is_enabled is not None:
        cursor.execute(
            "UPDATE system_settings SET scheduler_interval_seconds = ?, scheduler_enabled = ?, updated_at = ? WHERE id = 1;",
            (int(interval_seconds), 1 if is_enabled else 0, updated_at)
        )
    elif interval_seconds is not None:
        cursor.execute(
            "UPDATE system_settings SET scheduler_interval_seconds = ?, updated_at = ? WHERE id = 1;",
            (int(interval_seconds), updated_at)
        )
    elif is_enabled is not None:
        cursor.execute(
            "UPDATE system_settings SET scheduler_enabled = ?, updated_at = ? WHERE id = 1;",
            (1 if is_enabled else 0, updated_at)
        )
    conn.commit()
    conn.close()
    return True

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
        
        # Trích xuất chẩn đoán Agentic hoặc DOM nếu có
        diagnostic_summary = None
        if latest_row and latest_row.get("full_signals_json"):
            try:
                sig_data = json.loads(latest_row["full_signals_json"])
                if sig_data.get("agent"):
                    diagnostic_summary = sig_data["agent"].get("title") or sig_data["agent"].get("root_cause")
                elif sig_data.get("dom") and not sig_data["dom"].get("is_structure_valid", True):
                    diagnostic_summary = "Thiếu thành phần DOM: " + ", ".join(sig_data["dom"].get("missing_critical_elements", []))
            except Exception:
                diagnostic_summary = None

        site_summaries.append({
            "website_id": site["id"],
            "name": site["name"],
            "url": site["url"],
            "domain": site["domain"],
            "current_status": current_status,
            "diagnostic_summary": diagnostic_summary,
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

    # 4. Danh sách các sự cố trong khoảng thời gian
    incidents = []
    for r in rows:
        if r.get("overall_status") in ["CRITICAL", "WARNING"]:
            detail_msg = None
            if r.get("full_signals_json"):
                try:
                    sig = json.loads(r["full_signals_json"])
                    if sig.get("agent"):
                        detail_msg = sig["agent"].get("title") or sig["agent"].get("root_cause")
                    elif sig.get("dom") and not sig["dom"].get("is_structure_valid", True):
                        detail_msg = "DOM: " + ", ".join(sig["dom"].get("missing_critical_elements", []))
                except Exception:
                    detail_msg = None

            incidents.append({
                "timestamp": r["timestamp"],
                "website_name": r["website_name"],
                "status": r["overall_status"],
                "http_code": r["http_status_code"],
                "dns_resolved": r["dns_resolved"],
                "ssl_valid": r["ssl_is_valid"],
                "ssl_days": r["ssl_days_remaining"],
                "details": detail_msg or ("HTTP " + str(r.get("http_status_code") or "Error"))
            })
            if len(incidents) >= 50:
                break

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


# ==================== 5. GIÁM SÁT HIỆU NĂNG HỆ THỐNG & CHI PHÍ LLMOPS (OBSERVABILITY & COST) ====================

USD_TO_VND_RATE = 25400.0

def calculate_llm_cost(model: Optional[str], prompt_tokens: int, completion_tokens: int) -> float:
    """
    Tính toán chi phí LLM ước tính ($ USD) dựa trên biểu giá Google Gemini:
    - gemini-1.5-flash / gemini-flash-latest:
        Input: $0.075 / 1M tokens ($0.000000075 / token)
        Output: $0.30 / 1M tokens ($0.00000030 / token)
    - gemini-1.5-pro / gemini-pro-latest:
        Input: $1.25 / 1M tokens ($0.00000125 / token)
        Output: $5.00 / 1M tokens ($0.00000500 / token)
    """
    if not model or (prompt_tokens <= 0 and completion_tokens <= 0):
        return 0.0

    m_low = str(model).lower()
    if "pro" in m_low:
        rate_in = 1.25 / 1_000_000
        rate_out = 5.00 / 1_000_000
    else:
        # Flash rates (mặc định)
        rate_in = 0.075 / 1_000_000
        rate_out = 0.30 / 1_000_000

    cost = (prompt_tokens * rate_in) + (completion_tokens * rate_out)
    return round(cost, 6)

def save_system_telemetry(
    workflow_type: str,
    website_id: Optional[int] = None,
    website_name: Optional[str] = None,
    total_latency_ms: float = 0.0,
    probes_latency_ms: float = 0.0,
    llm_latency_ms: float = 0.0,
    llm_model: Optional[str] = None,
    llm_status: Optional[str] = None,
    prompt_tokens: int = 0,
    completion_tokens: int = 0,
    total_tokens: int = 0,
    fallback_to_kb: bool = False,
    self_correction_executed: bool = False,
    suppressed_alerts_count: int = 0,
    overall_severity: str = "HEALTHY"
) -> int:
    """Ghi nhận một bản ghi đo lường hiệu năng hệ thống, độ trễ và chi phí token vào system_telemetry_logs."""
    timestamp = datetime.now(TZ_VN).isoformat()
    estimated_cost = calculate_llm_cost(llm_model, prompt_tokens, completion_tokens)
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO system_telemetry_logs (
            timestamp, workflow_type, website_id, website_name,
            total_latency_ms, probes_latency_ms, llm_latency_ms,
            llm_model, llm_status, prompt_tokens, completion_tokens,
            total_tokens, estimated_cost_usd, fallback_to_kb,
            self_correction_executed, suppressed_alerts_count, overall_severity
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        timestamp, workflow_type, website_id, website_name,
        round(total_latency_ms, 2), round(probes_latency_ms, 2), round(llm_latency_ms, 2),
        llm_model or "None", llm_status or "NONE",
        prompt_tokens, completion_tokens, total_tokens,
        estimated_cost, 1 if fallback_to_kb else 0,
        1 if self_correction_executed else 0,
        suppressed_alerts_count, overall_severity
    ))
    row_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return row_id

def get_telemetry_metrics_summary(hours: int = 24) -> Dict[str, Any]:
    """
    Truy vấn và tổng hợp các chỉ số hiệu năng và chi phí của hệ thống trong khoảng thời gian:
    - Độ trễ P50, P95, Max (Workflow, Probes, LLM)
    - Tiêu thụ Token (Prompt, Completion, Total)
    - Chi phí ước tính ($ USD & VNĐ)
    - Tỷ lệ Fallback 0ms KB vs LLM Reasoning
    - Lịch sử chạy đo lường gần nhất
    """
    cutoff_time = (datetime.now(TZ_VN) - timedelta(hours=hours)).isoformat()
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT * FROM system_telemetry_logs
        WHERE timestamp >= ?
        ORDER BY id DESC
    """, (cutoff_time,))
    rows = cursor.fetchall()
    conn.close()

    total_runs = len(rows)
    if total_runs == 0:
        return {
            "period_hours": hours,
            "total_runs": 0,
            "avg_workflow_latency_ms": 0.0,
            "p95_workflow_latency_ms": 0.0,
            "max_workflow_latency_ms": 0.0,
            "avg_probes_latency_ms": 0.0,
            "avg_llm_latency_ms": 0.0,
            "total_prompt_tokens": 0,
            "total_completion_tokens": 0,
            "total_tokens": 0,
            "total_cost_usd": 0.0,
            "total_cost_vnd": 0.0,
            "llm_success_count": 0,
            "fallback_count": 0,
            "fallback_rate_pct": 0.0,
            "self_correction_count": 0,
            "total_suppressed_alerts": 0,
            "recent_logs": [],
            "models_breakdown": {},
            "websites_cost_breakdown": {}
        }

    total_latencies = [float(r["total_latency_ms"] or 0) for r in rows]
    probes_latencies = [float(r["probes_latency_ms"] or 0) for r in rows]
    llm_latencies = [float(r["llm_latency_ms"] or 0) for r in rows if r["llm_latency_ms"] and r["llm_latency_ms"] > 0]

    total_latencies_sorted = sorted(total_latencies)
    p95_idx = int(0.95 * len(total_latencies_sorted))
    p95_latency = total_latencies_sorted[min(p95_idx, len(total_latencies_sorted) - 1)]

    total_prompt_tokens = sum(int(r["prompt_tokens"] or 0) for r in rows)
    total_completion_tokens = sum(int(r["completion_tokens"] or 0) for r in rows)
    total_tokens = sum(int(r["total_tokens"] or 0) for r in rows)
    total_cost_usd = sum(float(r["estimated_cost_usd"] or 0) for r in rows)

    fallback_count = sum(1 for r in rows if r["fallback_to_kb"])
    fallback_rate_pct = round((fallback_count / total_runs) * 100, 1)
    llm_success_count = sum(1 for r in rows if r["llm_status"] == "SUCCESS")
    self_correction_count = sum(1 for r in rows if r["self_correction_executed"])
    suppressed_count = sum(int(r["suppressed_alerts_count"] or 0) for r in rows)

    # Phân bổ theo Model
    models_breakdown: Dict[str, Dict[str, Any]] = {}
    websites_cost: Dict[str, Dict[str, Any]] = {}

    for r in rows:
        m = r["llm_model"] or "None"
        if m not in models_breakdown:
            models_breakdown[m] = {"calls": 0, "tokens": 0, "cost_usd": 0.0}
        models_breakdown[m]["calls"] += 1
        models_breakdown[m]["tokens"] += int(r["total_tokens"] or 0)
        models_breakdown[m]["cost_usd"] += float(r["estimated_cost_usd"] or 0.0)

        site_name = r["website_name"] or "Unknown"
        if site_name not in websites_cost:
            websites_cost[site_name] = {"scans": 0, "tokens": 0, "cost_usd": 0.0, "avg_latency_ms": 0.0, "_latencies": []}
        websites_cost[site_name]["scans"] += 1
        websites_cost[site_name]["tokens"] += int(r["total_tokens"] or 0)
        websites_cost[site_name]["cost_usd"] += float(r["estimated_cost_usd"] or 0.0)
        websites_cost[site_name]["_latencies"].append(float(r["total_latency_ms"] or 0))

    for s_info in websites_cost.values():
        lats = s_info.pop("_latencies")
        s_info["avg_latency_ms"] = round(sum(lats) / len(lats), 1) if lats else 0.0
        s_info["cost_usd"] = round(s_info["cost_usd"], 6)

    for m_info in models_breakdown.values():
        m_info["cost_usd"] = round(m_info["cost_usd"], 6)

    recent_logs = [dict(r) for r in rows[:50]]

    return {
        "period_hours": hours,
        "total_runs": total_runs,
        "avg_workflow_latency_ms": round(sum(total_latencies) / total_runs, 1),
        "p95_workflow_latency_ms": round(p95_latency, 1),
        "max_workflow_latency_ms": round(max(total_latencies), 1),
        "avg_probes_latency_ms": round(sum(probes_latencies) / total_runs, 1),
        "avg_llm_latency_ms": round(sum(llm_latencies) / len(llm_latencies), 1) if llm_latencies else 0.0,
        "total_prompt_tokens": total_prompt_tokens,
        "total_completion_tokens": total_completion_tokens,
        "total_tokens": total_tokens,
        "total_cost_usd": round(total_cost_usd, 6),
        "total_cost_vnd": round(total_cost_usd * USD_TO_VND_RATE, 0),
        "llm_success_count": llm_success_count,
        "fallback_count": fallback_count,
        "fallback_rate_pct": fallback_rate_pct,
        "self_correction_count": self_correction_count,
        "total_suppressed_alerts": suppressed_count,
        "recent_logs": recent_logs,
        "models_breakdown": models_breakdown,
        "websites_cost_breakdown": websites_cost
    }

def get_storage_metrics() -> Dict[str, Any]:
    """Thống kê dung lượng lưu trữ thực tế của hệ thống (CSDL, Ảnh chụp, Diffs, Backups)."""
    from config import DB_PATH, DATA_DIR
    
    db_size_bytes = DB_PATH.stat().st_size if DB_PATH.exists() else 0
    
    screenshots_dir = Path(DATA_DIR) / "screenshots"
    diffs_dir = Path(DATA_DIR) / "visual_diffs"
    baselines_dir = Path(DATA_DIR) / "visual_baselines"
    backups_dir = Path(DATA_DIR) / "backups"

    def dir_stats(folder: Path):
        count = 0
        total_bytes = 0
        if folder.exists():
            for p in folder.glob("*"):
                if p.is_file():
                    count += 1
                    try:
                        total_bytes += p.stat().st_size
                    except Exception:
                        pass
        return count, round(total_bytes / (1024 * 1024), 2)

    sc_count, sc_mb = dir_stats(screenshots_dir)
    diff_count, diff_mb = dir_stats(diffs_dir)
    base_count, base_mb = dir_stats(baselines_dir)
    bak_count, bak_mb = dir_stats(backups_dir)

    total_storage_mb = round((db_size_bytes / (1024 * 1024)) + sc_mb + diff_mb + base_mb + bak_mb, 2)

    return {
        "db_size_mb": round(db_size_bytes / (1024 * 1024), 2),
        "db_size_bytes": db_size_bytes,
        "screenshots_count": sc_count,
        "screenshots_size_mb": sc_mb,
        "visual_diffs_count": diff_count,
        "visual_diffs_size_mb": diff_mb,
        "baselines_count": base_count,
        "baselines_size_mb": base_mb,
        "backups_count": bak_count,
        "backups_size_mb": bak_mb,
        "total_storage_mb": total_storage_mb
    }


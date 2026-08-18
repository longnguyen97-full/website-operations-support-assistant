import time
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger

from tools.http_checker import check_http
from tools.dns_checker import check_dns
from tools.ssl_checker import check_ssl
from database.repository import (
    get_all_websites,
    get_active_baseline,
    save_monitoring_log,
    calculate_overall_status,
    purge_old_logs
)
from notifications.email_service import check_and_send_alert

JOB_ID = "website_periodic_monitoring_job"
TZ_VN = timezone(timedelta(hours=7))

# Global state tracker
_scheduler: Optional[BackgroundScheduler] = None
_scheduler_state = {
    "interval_seconds": 60,
    "last_run_time": None,
    "last_run_summary": None,
    "total_runs": 0
}

def execute_single_website_check(site: dict) -> dict:
    """Thực hiện đầy đủ quy trình kiểm tra 3 probes cho 1 website và lưu vào CSDL."""
    active_b = get_active_baseline(site["id"])
    baseline_dns = active_b.get("baseline_dns") if active_b else None
    expected_status = (
        active_b.get("expected_http_status")
        if active_b and active_b.get("expected_http_status")
        else site.get("expected_status", 200)
    )

    # 1. Chạy 3 Tools
    http_res = check_http(site["url"], expected_status=expected_status)
    dns_res = check_dns(site["domain"], baseline=baseline_dns)
    ssl_res = check_ssl(site["url"])

    # 2. Ghi nhật ký vào CSDL
    log_id = save_monitoring_log(
        website_id=site["id"],
        website_name=site["name"],
        http_res=http_res,
        dns_res=dns_res,
        ssl_res=ssl_res
    )

    # 3. Kích hoạt cảnh báo Email nếu có sự cố hoặc phục hồi
    overall_status = calculate_overall_status(http_res, dns_res, ssl_res)
    try:
        check_and_send_alert(site, overall_status, http_res, dns_res, ssl_res)
    except Exception as e:
        print(f"Warning: Lỗi gửi email alert cho {site['name']}: {e}")

    return {
        "website_id": site["id"],
        "name": site["name"],
        "log_id": log_id,
        "overall_status": overall_status,
        "http_ok": http_res.get("is_expected_status", False),
        "dns_ok": dns_res.get("resolved", False),
        "ssl_ok": ssl_res.get("is_valid", False)
    }

def run_all_monitors_job():
    """Hàm tác vụ được APScheduler gọi định kỳ để quét toàn bộ website trong CSDL."""
    now_iso = datetime.now(TZ_VN).isoformat()
    _scheduler_state["last_run_time"] = now_iso
    _scheduler_state["total_runs"] += 1
    
    websites = get_all_websites()
    if not websites:
        _scheduler_state["last_run_summary"] = "Không có website nào trong CSDL để quét."
        return

    results = []
    for site in websites:
        try:
            res = execute_single_website_check(site)
            results.append(res)
        except Exception as e:
            results.append({
                "website_id": site.get("id"),
                "name": site.get("name"),
                "error": str(e)
            })

    # Định kỳ dọn log cũ hơn 30 ngày (Data Retention Policy)
    try:
        purge_old_logs(days_to_keep=30)
    except Exception:
        pass

    _scheduler_state["last_run_summary"] = f"Đã quét thành công {len(results)} website lúc {now_iso}."

REPORT_JOB_ID = "daily_report_checker_job"

def check_and_send_scheduled_reports_job():
    """Kiểm tra và gửi báo cáo định kỳ theo giờ cấu hình trong email_settings."""
    from database.repository import get_email_settings
    from notifications.email_service import send_periodic_report_email

    settings = get_email_settings()
    if not settings.get("is_enabled") or not settings.get("enable_daily_report"):
        return

    report_time_str = settings.get("daily_report_time", "08:00").strip()
    now = datetime.now(TZ_VN)
    current_hm = now.strftime("%H:%M")
    
    # Kiểm tra xem đã đến giờ gửi chưa
    if current_hm == report_time_str:
        last_sent = settings.get("last_report_sent_at")
        # Kiểm tra xem hôm nay đã gửi chưa
        today_str = now.strftime("%Y-%m-%d")
        if not last_sent or not str(last_sent).startswith(today_str):
            try:
                send_periodic_report_email(hours=24, settings=settings)
            except Exception as e:
                print(f"Warning: Lỗi gửi báo cáo định kỳ: {e}")

def get_scheduler() -> BackgroundScheduler:
    """Khởi tạo hoặc lấy đối tượng Singleton BackgroundScheduler với Timezone UTC+7."""
    global _scheduler
    if _scheduler is None:
        _scheduler = BackgroundScheduler(daemon=True, timezone=TZ_VN)
    return _scheduler

def start_background_scheduler(interval_seconds: int = 60):
    """Bắt đầu chạy scheduler định kỳ với khoảng thời gian (giây)."""
    sched = get_scheduler()
    _scheduler_state["interval_seconds"] = interval_seconds

    # 1. Thêm hoặc cập nhật job quét probes định kỳ
    trigger = IntervalTrigger(seconds=interval_seconds, timezone=TZ_VN)
    if sched.get_job(JOB_ID):
        sched.reschedule_job(JOB_ID, trigger=trigger)
    else:
        sched.add_job(
            run_all_monitors_job,
            trigger=trigger,
            id=JOB_ID,
            name="Website Periodic Probes Monitoring",
            replace_existing=True
        )

    # 2. Thêm job kiểm tra gửi Báo cáo Định kỳ hàng ngày (quét mỗi phút)
    if not sched.get_job(REPORT_JOB_ID):
        sched.add_job(
            check_and_send_scheduled_reports_job,
            trigger=IntervalTrigger(minutes=1, timezone=TZ_VN),
            id=REPORT_JOB_ID,
            name="Daily Scheduled Health Report Check",
            replace_existing=True
        )

    if not sched.running:
        sched.start()

def stop_background_scheduler():
    """Tạm dừng / Dừng background scheduler."""
    sched = get_scheduler()
    if sched.running:
        sched.pause()

def resume_background_scheduler():
    """Tiếp tục chạy scheduler nếu đang pause."""
    sched = get_scheduler()
    if sched.running:
        sched.resume()
    else:
        start_background_scheduler(_scheduler_state["interval_seconds"])

def update_scheduler_interval(interval_seconds: int):
    """Cập nhật tần suất quét (interval) của scheduler."""
    _scheduler_state["interval_seconds"] = interval_seconds
    sched = get_scheduler()
    if sched.get_job(JOB_ID):
        sched.reschedule_job(JOB_ID, trigger=IntervalTrigger(seconds=interval_seconds, timezone=TZ_VN))

def run_monitors_now():
    """Kích hoạt quét toàn bộ website ngay lập tức ngoài chu kỳ."""
    run_all_monitors_job()

def send_periodic_report_now(hours: int = 24):
    """Kích hoạt tổng hợp và gửi Báo cáo Định kỳ ngay lập tức."""
    from notifications.email_service import send_periodic_report_email
    return send_periodic_report_email(hours=hours)

def get_scheduler_info() -> Dict[str, Any]:
    """Trả về trạng thái hiện tại của Scheduler theo giờ UTC+7."""
    sched = get_scheduler()
    job = sched.get_job(JOB_ID) if sched else None
    
    is_active = sched.running and (job is not None)
    next_run = None
    if job and job.next_run_time:
        next_run = job.next_run_time.astimezone(TZ_VN).strftime("%Y-%m-%d %H:%M:%S")

    return {
        "is_running": is_active,
        "interval_seconds": _scheduler_state["interval_seconds"],
        "next_run_time": next_run,
        "last_run_time": _scheduler_state["last_run_time"],
        "last_run_summary": _scheduler_state["last_run_summary"],
        "total_runs": _scheduler_state["total_runs"]
    }

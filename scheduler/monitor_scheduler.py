import time
import asyncio
import threading
from datetime import datetime
from typing import Optional, Dict, Any, List
from apscheduler.schedulers.asyncio import AsyncIOScheduler
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
    purge_old_logs,
    get_system_settings,
    update_scheduler_settings,
    save_system_telemetry
)
from notifications.email_service import check_and_send_alert
from config import (
    TZ_VN,
    DEFAULT_SCHEDULER_INTERVAL_SECONDS,
    DATA_RETENTION_DAYS,
    HTTP_TIMEOUT_SECONDS,
    DNS_TIMEOUT_SECONDS,
    SSL_TIMEOUT_SECONDS
)

JOB_ID = "website_periodic_monitoring_job"
REPORT_JOB_ID = "daily_report_checker_job"

# Cấu hình giới hạn kiểm soát đồng thời (Concurrency Control) bảo đảm hiệu năng hệ thống
DEFAULT_CONCURRENCY_SEMAPHORE_LIMIT = 10

# Biến toàn cục quản lý Event Loop và Scheduler
_event_loop: Optional[asyncio.AbstractEventLoop] = None
_loop_thread: Optional[threading.Thread] = None
_scheduler: Optional[AsyncIOScheduler] = None

# Global state tracker
_scheduler_state = {
    "interval_seconds": DEFAULT_SCHEDULER_INTERVAL_SECONDS,
    "last_run_time": None,
    "last_run_summary": None,
    "total_runs": 0,
    "is_paused": False,
    "concurrency_limit": DEFAULT_CONCURRENCY_SEMAPHORE_LIMIT
}

def _ensure_background_event_loop() -> asyncio.AbstractEventLoop:
    """Khởi tạo và duy trì vòng lặp sự kiện bất đồng bộ asyncio trong luồng nền Daemon."""
    global _event_loop, _loop_thread
    if _event_loop is None or not _event_loop.is_running():
        _event_loop = asyncio.new_event_loop()
        def _run_loop(loop: asyncio.AbstractEventLoop):
            asyncio.set_event_loop(loop)
            loop.run_forever()
        _loop_thread = threading.Thread(target=_run_loop, args=(_event_loop,), daemon=True, name="AsyncIOSchedulerLoopThread")
        _loop_thread.start()
        # Chờ vòng lặp sẵn sàng
        while not _event_loop.is_running():
            time.sleep(0.01)
    return _event_loop

def execute_single_website_telemetry(site: dict, sys_settings: Optional[dict] = None) -> dict:
    """
    Thu thập telemetry 3 probes cho 1 website và ghi log vào CSDL SQLite.
    Tách biệt hoàn toàn việc gửi cảnh báo (Decoupled Telemetry Collection).
    """
    start_t = time.time()
    if sys_settings is None:
        sys_settings = get_system_settings()

    http_timeout = float(sys_settings.get("http_timeout_seconds") or HTTP_TIMEOUT_SECONDS)
    dns_timeout = float(sys_settings.get("dns_timeout_seconds") or DNS_TIMEOUT_SECONDS)
    ssl_timeout = float(sys_settings.get("ssl_timeout_seconds") or SSL_TIMEOUT_SECONDS)

    active_b = get_active_baseline(site["id"])
    baseline_dns = active_b.get("baseline_dns") if active_b else None
    expected_status = (
        active_b.get("expected_http_status")
        if active_b and active_b.get("expected_http_status")
        else site.get("expected_status", 200)
    )

    # 1. Chạy Tools đo kiểm với timeout động
    http_res = check_http(site["url"], expected_status=expected_status, timeout=http_timeout)
    dns_res = check_dns(site["domain"], baseline=baseline_dns, timeout=dns_timeout)
    ssl_res = check_ssl(site["url"], timeout=ssl_timeout)

    # 1b. Quét DOM nhanh qua BS4 parser
    dom_res = None
    if http_res.get("status_code") == 200:
        try:
            from tools.dom_validator import validate_dom
            dom_res = validate_dom(site["url"], use_browser=False, timeout=5.0)
        except Exception:
            dom_res = None

    overall_status = calculate_overall_status(http_res, dns_res, ssl_res, dom_res=dom_res)

    # 2. Ghi nhật ký đo kiểm vào CSDL
    log_id = save_monitoring_log(
        website_id=site["id"],
        website_name=site["name"],
        http_res=http_res,
        dns_res=dns_res,
        ssl_res=ssl_res,
        dom_res=dom_res,
        overall_status=overall_status
    )

    # Chuẩn bị payload cảnh báo nếu cần gửi
    alert_payload = None
    if overall_status in ["CRITICAL", "WARNING"]:
        rca_ctx = None
        try:
            from analytics.anomaly_detector import AnomalyDetectionOrchestrator
            from agents.analysis_agent import IncidentAnalysisAgent

            det_orch = AnomalyDetectionOrchestrator()
            diag_res = det_orch.run_multi_signal_rule_statistical(
                http_res=http_res,
                dns_res=dns_res,
                ssl_res=ssl_res,
                dom_res=dom_res
            )

            analysis_agent = IncidentAnalysisAgent()
            rca_ctx = analysis_agent.analyze_incident(
                website_info=site,
                correlation_data={
                    "incident_type": diag_res.get("incident_type"),
                    "overall_severity": diag_res.get("overall_status", overall_status),
                    "has_incident": diag_res.get("is_anomaly_detected", True),
                    "root_cause_summary": diag_res.get("root_cause_summary"),
                    "primary_issue": diag_res.get("primary_issue"),
                    "correlated_signals": diag_res.get("correlated_signals", [])
                },
                evidence_data={
                    "http": http_res,
                    "dns": dns_res,
                    "ssl": ssl_res,
                    "dom": dom_res
                }
            )
        except Exception as e:
            print(f"Warning: Lỗi tạo RCA context: {e}")

        alert_payload = {
            "site": site,
            "overall_status": overall_status,
            "http_res": http_res,
            "dns_res": dns_res,
            "ssl_res": ssl_res,
            "rca_report": rca_ctx
        }

    elapsed_ms = round((time.time() - start_t) * 1000, 2)
    http_ms = float(http_res.get("response_time_ms") or 0.0)
    dns_ms = float(dns_res.get("resolution_time_ms") or 0.0)
    probes_ms = round(http_ms + dns_ms, 2)
    llm_telemetry = (alert_payload.get("rca_report") or {}).get("llm_telemetry", {}) if alert_payload else {}

    try:
        save_system_telemetry(
            workflow_type="SCHEDULED_JOB",
            website_id=site.get("id"),
            website_name=site.get("name"),
            total_latency_ms=elapsed_ms,
            probes_latency_ms=probes_ms,
            llm_latency_ms=llm_telemetry.get("latency_ms", 0.0),
            llm_model=llm_telemetry.get("model"),
            llm_status=llm_telemetry.get("status"),
            prompt_tokens=llm_telemetry.get("prompt_tokens", 0),
            completion_tokens=llm_telemetry.get("completion_tokens", 0),
            total_tokens=llm_telemetry.get("total_tokens", 0),
            fallback_to_kb=llm_telemetry.get("fallback_to_kb", True),
            self_correction_executed=False,
            suppressed_alerts_count=0,
            overall_severity=overall_status
        )
    except Exception as ex:
        print(f"Warning: Lỗi ghi nhận telemetry background: {ex}")

    summary = {
        "website_id": site["id"],
        "name": site["name"],
        "log_id": log_id,
        "overall_status": overall_status,
        "http_ok": http_res.get("is_expected_status", False),
        "dns_ok": dns_res.get("resolved", False),
        "ssl_ok": ssl_res.get("is_valid", False)
    }

    return {
        "summary": summary,
        "alert_payload": alert_payload
    }

def execute_single_website_check(site: dict, sys_settings: Optional[dict] = None) -> dict:
    """Hàm kiểm tra đơn lẻ đồng bộ tương thích ngược với các caller cũ."""
    res = execute_single_website_telemetry(site, sys_settings=sys_settings)
    payload = res.get("alert_payload")
    if payload:
        try:
            check_and_send_alert(
                payload["site"],
                payload["overall_status"],
                payload["http_res"],
                payload["dns_res"],
                payload["ssl_res"],
                rca_report=payload.get("rca_report")
            )
        except Exception as e:
            print(f"Warning: Lỗi gửi email alert cho {payload['site']['name']}: {e}")
    return res["summary"]

async def run_all_monitors_job_async(concurrency_limit: int = DEFAULT_CONCURRENCY_SEMAPHORE_LIMIT):
    """
    Tác vụ quét ngầm bất đồng bộ kết hợp asyncio.Semaphore(10):
    - Kiểm soát đồng thời tối đa 10 phiên đo kiểm song song tại một thời điểm
      tránh nghẽn CPU và băng thông mạng cục bộ khi giám sát số lượng lớn website.
    - Phân tách ranh giới giữa thu thập telemetry và hàng đợi phát tán email cảnh báo.
    """
    now_iso = datetime.now(TZ_VN).isoformat()
    _scheduler_state["last_run_time"] = now_iso
    _scheduler_state["total_runs"] += 1

    websites = get_all_websites()
    if not websites:
        _scheduler_state["last_run_summary"] = "Không có website nào trong CSDL để quét."
        return []

    sys_settings = get_system_settings()

    # Khởi tạo Semaphore kiểm soát giới hạn luồng quét đồng thời (mặc định 10)
    semaphore = asyncio.Semaphore(concurrency_limit)
    alert_queue: asyncio.Queue = asyncio.Queue()

    async def _worker(site: dict):
        async with semaphore:
            # Đo kiểm bất đồng bộ thông qua thread pool
            try:
                res = await asyncio.to_thread(execute_single_website_telemetry, site, sys_settings)
                if res.get("alert_payload"):
                    await alert_queue.put(res["alert_payload"])
                return res["summary"]
            except Exception as e:
                return {
                    "website_id": site.get("id"),
                    "name": site.get("name"),
                    "error": str(e)
                }

    tasks = [_worker(site) for site in websites]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    # Xử lý hàng đợi phát tán Email cảnh báo tách rời (Decoupled Background Dispatch)
    async def _dispatch_alerts_worker():
        while not alert_queue.empty():
            item = await alert_queue.get()
            try:
                await asyncio.to_thread(
                    check_and_send_alert,
                    item["site"],
                    item["overall_status"],
                    item["http_res"],
                    item["dns_res"],
                    item["ssl_res"],
                    rca_report=item.get("rca_report")
                )
            except Exception as ex:
                print(f"Warning: Lỗi phát tán email cảnh báo: {ex}")
            finally:
                alert_queue.task_done()

    # Xử lý hàng đợi gửi email bất đồng bộ tách rời (Decoupled Alert Dispatch)
    if not alert_queue.empty():
        await _dispatch_alerts_worker()

    # Định kỳ dọn log cũ hơn số ngày quy định (Data Retention Policy)
    try:
        purge_old_logs(days_to_keep=DATA_RETENTION_DAYS)
    except Exception:
        pass

    _scheduler_state["last_run_summary"] = f"Đã quét thành công {len(results)} website (Semaphore Concurrency: {concurrency_limit}) lúc {now_iso}."
    return results

def run_all_monitors_job():
    """Hàm tác vụ đồng bộ cho phép kích hoạt quét toàn bộ websites với Semaphore(10)."""
    loop = _ensure_background_event_loop()
    future = asyncio.run_coroutine_threadsafe(
        run_all_monitors_job_async(concurrency_limit=DEFAULT_CONCURRENCY_SEMAPHORE_LIMIT),
        loop
    )
    return future.result()

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

    if current_hm == report_time_str:
        last_sent = settings.get("last_report_sent_at")
        today_str = now.strftime("%Y-%m-%d")
        if not last_sent or not str(last_sent).startswith(today_str):
            try:
                send_periodic_report_email(hours=24, settings=settings)
            except Exception as e:
                print(f"Warning: Lỗi gửi báo cáo định kỳ: {e}")

async def check_and_send_scheduled_reports_job_async():
    """Phiên bản bất đồng bộ của job báo cáo định kỳ."""
    await asyncio.to_thread(check_and_send_scheduled_reports_job)

def get_scheduler() -> AsyncIOScheduler:
    """Khởi tạo hoặc lấy đối tượng Singleton AsyncIOScheduler với Timezone UTC+7."""
    global _scheduler
    if _scheduler is None:
        loop = _ensure_background_event_loop()
        _scheduler = AsyncIOScheduler(event_loop=loop, timezone=TZ_VN)
    return _scheduler

def start_background_scheduler(interval_seconds: Optional[int] = None):
    """Bắt đầu chạy AsyncIOScheduler định kỳ với khoảng thời gian (giây) - Mặc định lấy từ CSDL."""
    sys_settings = get_system_settings()
    if interval_seconds is None:
        interval_seconds = int(sys_settings.get("scheduler_interval_seconds") or DEFAULT_SCHEDULER_INTERVAL_SECONDS)

    sched = get_scheduler()
    _scheduler_state["interval_seconds"] = interval_seconds

    # 1. Thêm hoặc cập nhật job quét probes định kỳ bất đồng bộ
    trigger = IntervalTrigger(seconds=interval_seconds, timezone=TZ_VN)
    if sched.get_job(JOB_ID):
        sched.reschedule_job(JOB_ID, trigger=trigger)
    else:
        sched.add_job(
            run_all_monitors_job_async,
            trigger=trigger,
            id=JOB_ID,
            name="Website Periodic Probes Monitoring (AsyncIO Concurrency Control)",
            replace_existing=True
        )

    # 2. Thêm job kiểm tra gửi Báo cáo Định kỳ hàng ngày (quét mỗi phút)
    if not sched.get_job(REPORT_JOB_ID):
        sched.add_job(
            check_and_send_scheduled_reports_job_async,
            trigger=IntervalTrigger(minutes=1, timezone=TZ_VN),
            id=REPORT_JOB_ID,
            name="Daily Scheduled Health Report Check",
            replace_existing=True
        )

    if not sched.running:
        sched.start()

    # Kiểm tra cấu hình trạng thái bật/tắt (scheduler_enabled) từ CSDL
    is_enabled = bool(sys_settings.get("scheduler_enabled", 1))
    job = sched.get_job(JOB_ID)
    if not is_enabled:
        if job:
            job.pause()
        _scheduler_state["is_paused"] = True
    else:
        if job and job.next_run_time is None:
            job.resume()
        _scheduler_state["is_paused"] = False

def stop_background_scheduler():
    """Dừng quét nền định kỳ (Dừng quét)."""
    sched = get_scheduler()
    job = sched.get_job(JOB_ID) if sched else None
    if job:
        job.pause()
    _scheduler_state["is_paused"] = True
    try:
        update_scheduler_settings(is_enabled=False)
    except Exception as e:
        print(f"Warning: Không thể lưu trạng thái dừng quét vào CSDL: {e}")

def resume_background_scheduler():
    """Bắt đầu / Tiếp tục quét nền định kỳ."""
    sched = get_scheduler()
    if not sched.running:
        sched.start()
    job = sched.get_job(JOB_ID) if sched else None
    if job:
        job.resume()
    else:
        trigger = IntervalTrigger(seconds=_scheduler_state["interval_seconds"], timezone=TZ_VN)
        sched.add_job(
            run_all_monitors_job_async,
            trigger=trigger,
            id=JOB_ID,
            name="Website Periodic Probes Monitoring (AsyncIO Concurrency Control)",
            replace_existing=True
        )
    _scheduler_state["is_paused"] = False
    try:
        update_scheduler_settings(is_enabled=True)
    except Exception as e:
        print(f"Warning: Không thể lưu trạng thái tiếp tục quét vào CSDL: {e}")

def update_scheduler_interval(interval_seconds: int, persist_db: bool = True):
    """Cập nhật tần suất quét (interval) của scheduler và lưu bền vững vào CSDL."""
    _scheduler_state["interval_seconds"] = interval_seconds
    sched = get_scheduler()
    job = sched.get_job(JOB_ID) if sched else None
    if job:
        sched.reschedule_job(JOB_ID, trigger=IntervalTrigger(seconds=interval_seconds, timezone=TZ_VN))
        if _scheduler_state.get("is_paused"):
            job.pause()
    else:
        trigger = IntervalTrigger(seconds=interval_seconds, timezone=TZ_VN)
        sched.add_job(
            run_all_monitors_job_async,
            trigger=trigger,
            id=JOB_ID,
            name="Website Periodic Probes Monitoring (AsyncIO Concurrency Control)",
            replace_existing=True
        )
        if _scheduler_state.get("is_paused"):
            new_job = sched.get_job(JOB_ID)
            if new_job:
                new_job.pause()

    if persist_db:
        try:
            update_scheduler_settings(interval_seconds=interval_seconds)
        except Exception as e:
            print(f"Warning: Không thể lưu chu kỳ quét mới vào CSDL: {e}")

def run_monitors_now():
    """Kích hoạt quét toàn bộ website ngay lập tức ngoài chu kỳ thông qua Event Loop."""
    loop = _ensure_background_event_loop()
    future = asyncio.run_coroutine_threadsafe(
        run_all_monitors_job_async(concurrency_limit=DEFAULT_CONCURRENCY_SEMAPHORE_LIMIT),
        loop
    )
    return future

def send_periodic_report_now(hours: int = 24):
    """Kích hoạt tổng hợp và gửi Báo cáo Định kỳ ngay lập tức."""
    from notifications.email_service import send_periodic_report_email
    return send_periodic_report_email(hours=hours)

def get_scheduler_info() -> Dict[str, Any]:
    """Trả về trạng thái hiện tại của Scheduler theo giờ UTC+7."""
    sched = get_scheduler()
    job = sched.get_job(JOB_ID) if sched else None

    is_paused = _scheduler_state.get("is_paused", False)
    if not is_paused and job is not None and job.next_run_time is None:
        is_paused = True

    is_active = sched.running and (job is not None) and (not is_paused) and (job.next_run_time is not None)

    next_run = None
    if is_active and job and job.next_run_time:
        next_run = job.next_run_time.astimezone(TZ_VN).strftime("%Y-%m-%d %H:%M:%S")

    return {
        "is_running": is_active,
        "interval_seconds": _scheduler_state["interval_seconds"],
        "next_run_time": next_run,
        "last_run_time": _scheduler_state["last_run_time"],
        "last_run_summary": _scheduler_state["last_run_summary"],
        "total_runs": _scheduler_state["total_runs"],
        "concurrency_limit": _scheduler_state["concurrency_limit"],
        "scheduler_type": "AsyncIOScheduler (asyncio.Semaphore(10))"
    }

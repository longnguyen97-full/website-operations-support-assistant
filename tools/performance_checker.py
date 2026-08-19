import time
import socket
import ssl
from urllib.parse import urlparse
from typing import Optional, Dict, Any
from config import HTTP_TIMEOUT_SECONDS, DEFAULT_USER_AGENT

# Ngưỡng hiệu năng mặc định (SRE SLA Thresholds)
DEFAULT_WARNING_THRESHOLD_MS = 2000.0
DEFAULT_CRITICAL_THRESHOLD_MS = 5000.0
DEFAULT_DEGRADATION_RATIO_THRESHOLD = 0.5  # Tăng > 50% so với baseline coi là suy giảm

def _calculate_grade(total_time_ms: float) -> str:
    """Xếp loại hiệu năng theo chuẩn SRE."""
    if total_time_ms <= 500:
        return "A (Excellent)"
    elif total_time_ms <= 1000:
        return "B (Good)"
    elif total_time_ms <= 2000:
        return "C (Acceptable)"
    elif total_time_ms <= 4000:
        return "D (Slow)"
    else:
        return "F (Poor)"

def _check_performance_playwright(
    url: str,
    timeout_seconds: float = 15.0
) -> Optional[Dict[str, Any]]:
    """
    Đo lường thời gian tải trang thực tế trên trình duyệt bằng Playwright & Navigation Timing API.
    """
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(user_agent=DEFAULT_USER_AGENT)
            page = context.new_page()

            start_t = time.time()
            response = page.goto(url, timeout=int(timeout_seconds * 1000), wait_until="load")
            total_elapsed_ms = round((time.time() - start_t) * 1000, 2)

            status_code = response.status if response else None

            # Trích xuất Navigation Timing API từ trình duyệt
            nav_timing = page.evaluate("""() => {
                const nav = performance.getEntriesByType('navigation')[0];
                if (!nav) return null;
                return {
                    dns_time_ms: Math.max(0, nav.domainLookupEnd - nav.domainLookupStart),
                    tcp_time_ms: Math.max(0, nav.connectEnd - nav.connectStart),
                    ssl_time_ms: nav.secureConnectionStart > 0 ? Math.max(0, nav.connectEnd - nav.secureConnectionStart) : 0,
                    ttfb_ms: Math.max(0, nav.responseStart - nav.requestStart),
                    download_time_ms: Math.max(0, nav.responseEnd - nav.responseStart),
                    dom_interactive_ms: Math.max(0, nav.domInteractive - nav.startTime),
                    dom_content_loaded_ms: Math.max(0, nav.domContentLoadedEventEnd - nav.startTime),
                    load_event_ms: Math.max(0, nav.loadEventEnd - nav.startTime),
                    transfer_size_bytes: nav.transferSize || 0,
                    encoded_body_size_bytes: nav.encodedBodySize || 0,
                    decoded_body_size_bytes: nav.decodedBodySize || 0
                };
            }""")

            # Đếm số tài nguyên được tải (Sub-resources)
            resource_count = page.evaluate("""() => performance.getEntriesByType('resource').length""")

            browser.close()

            breakdown = {
                "dns_lookup_ms": round(nav_timing.get("dns_time_ms", 0.0), 2) if nav_timing else 0.0,
                "tcp_connect_ms": round(nav_timing.get("tcp_time_ms", 0.0), 2) if nav_timing else 0.0,
                "ssl_handshake_ms": round(nav_timing.get("ssl_time_ms", 0.0), 2) if nav_timing else 0.0,
                "ttfb_ms": round(nav_timing.get("ttfb_ms", 0.0), 2) if nav_timing else 0.0,
                "download_time_ms": round(nav_timing.get("download_time_ms", 0.0), 2) if nav_timing else 0.0,
                "dom_interactive_ms": round(nav_timing.get("dom_interactive_ms", 0.0), 2) if nav_timing else 0.0,
                "dom_content_loaded_ms": round(nav_timing.get("dom_content_loaded_ms", 0.0), 2) if nav_timing else 0.0,
                "load_event_ms": round(nav_timing.get("load_event_ms", 0.0), 2) if nav_timing else 0.0,
            }

            return {
                "source": "playwright_browser",
                "status_code": status_code,
                "total_time_ms": total_elapsed_ms,
                "ttfb_ms": breakdown["ttfb_ms"],
                "dom_content_loaded_ms": breakdown["dom_content_loaded_ms"],
                "page_load_ms": breakdown["load_event_ms"] or total_elapsed_ms,
                "resource_count": resource_count,
                "transfer_size_bytes": nav_timing.get("transfer_size_bytes", 0) if nav_timing else 0,
                "breakdown": breakdown
            }
    except Exception:
        return None

def _check_performance_httpx_socket(
    url: str,
    timeout_seconds: float = 10.0
) -> Dict[str, Any]:
    """
    Đo lường thời gian phản hồi chi tiết theo từng giai đoạn (DNS -> TCP -> TLS -> TTFB -> Download) bằng Socket & HTTPX.
    """
    import httpx

    parsed = urlparse(url if "://" in url else f"http://{url}")
    hostname = parsed.hostname or url
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    is_https = parsed.scheme == "https"

    breakdown = {
        "dns_lookup_ms": 0.0,
        "tcp_connect_ms": 0.0,
        "ssl_handshake_ms": 0.0,
        "ttfb_ms": 0.0,
        "download_time_ms": 0.0
    }

    # 1. DNS Timing
    t0 = time.time()
    try:
        ip = socket.gethostbyname(hostname)
        t_dns = time.time()
        breakdown["dns_lookup_ms"] = round((t_dns - t0) * 1000, 2)
    except Exception:
        ip = None
        t_dns = time.time()

    # 2. TCP & SSL Timing (nếu phân giải được IP)
    if ip:
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(timeout_seconds)
            t_tcp_start = time.time()
            sock.connect((ip, port))
            t_tcp_end = time.time()
            breakdown["tcp_connect_ms"] = round((t_tcp_end - t_tcp_start) * 1000, 2)

            if is_https:
                ctx = ssl.create_default_context()
                t_ssl_start = time.time()
                with ctx.wrap_socket(sock, server_hostname=hostname) as ssock:
                    t_ssl_end = time.time()
                    breakdown["ssl_handshake_ms"] = round((t_ssl_end - t_ssl_start) * 1000, 2)
            else:
                sock.close()
        except Exception:
            pass

    # 3. HTTP Request & TTFB via HTTPX
    start_req = time.time()
    with httpx.Client(follow_redirects=True, timeout=timeout_seconds) as client:
        resp = client.get(url, headers={"User-Agent": DEFAULT_USER_AGENT})
        total_time_ms = round(resp.elapsed.total_seconds() * 1000, 2)
        content_size = len(resp.content)

        # Ước lượng TTFB từ elapsed trừ đi thời gian kết nối
        ttfb_ms = max(5.0, total_time_ms - breakdown["download_time_ms"])
        breakdown["ttfb_ms"] = round(ttfb_ms, 2)

        return {
            "source": "synthetic_http",
            "status_code": resp.status_code,
            "total_time_ms": total_time_ms,
            "ttfb_ms": breakdown["ttfb_ms"],
            "dom_content_loaded_ms": None,
            "page_load_ms": total_time_ms,
            "resource_count": 1,
            "transfer_size_bytes": content_size,
            "breakdown": breakdown
        }

def check_performance(
    url: str,
    baseline_metrics: Optional[Dict[str, Any]] = None,
    warning_threshold_ms: float = DEFAULT_WARNING_THRESHOLD_MS,
    critical_threshold_ms: float = DEFAULT_CRITICAL_THRESHOLD_MS,
    use_browser: bool = True,
    timeout: float = 15.0
) -> Dict[str, Any]:
    """
    Công cụ Performance Monitoring dựa trên chuẩn SRE & Synthetic Monitoring (RULE_BUILD_TOOLS.md mục 4).
    
    Tham số:
    - url: Địa chỉ website cần đo lường.
    - baseline_metrics: Dữ liệu baseline lịch sử (chứa baseline_total_time_ms hoặc baseline_ttfb_ms).
    - warning_threshold_ms: Ngưỡng cảnh báo hiệu năng suy giảm (mặc định 2000ms).
    - critical_threshold_ms: Ngưỡng sự cố hiệu năng nghiêm trọng (mặc định 5000ms).
    - use_browser: Có sử dụng Playwright để đo thời gian tải trang thực tế hay không.
    - timeout: Thời gian chờ tối đa.
    """
    result = {
        "url": url,
        "total_time_ms": 0.0,
        "ttfb_ms": 0.0,
        "dom_content_loaded_ms": None,
        "page_load_ms": 0.0,
        "resource_count": 0,
        "transfer_size_bytes": 0,
        "performance_grade": "Unknown",
        "is_degraded": False,
        "degradation_severity": "HEALTHY",  # HEALTHY, WARNING, CRITICAL
        "degradation_reason": None,
        "breakdown": {},
        "monitoring_source": "synthetic",
        "baseline_comparison": {},
        "error": None
    }

    try:
        # Thử đo lường bằng Playwright nếu được yêu cầu
        metrics = None
        if use_browser:
            metrics = _check_performance_playwright(url, timeout_seconds=timeout)
        
        # Fallback qua HTTPX / Socket nếu Playwright không chạy hoặc use_browser=False
        if not metrics:
            metrics = _check_performance_httpx_socket(url, timeout_seconds=min(timeout, 10.0))

        result["monitoring_source"] = metrics["source"]
        result["total_time_ms"] = metrics["total_time_ms"]
        result["ttfb_ms"] = metrics["ttfb_ms"]
        result["dom_content_loaded_ms"] = metrics.get("dom_content_loaded_ms")
        result["page_load_ms"] = metrics["page_load_ms"]
        result["resource_count"] = metrics["resource_count"]
        result["transfer_size_bytes"] = metrics["transfer_size_bytes"]
        result["breakdown"] = metrics["breakdown"]
        result["performance_grade"] = _calculate_grade(result["total_time_ms"])

        # 1. Đánh giá suy giảm hiệu năng theo Ngưỡng Tĩnh (Static Thresholds)
        if result["total_time_ms"] >= critical_threshold_ms:
            result["is_degraded"] = True
            result["degradation_severity"] = "CRITICAL"
            result["degradation_reason"] = (
                f"Thời gian phản hồi ({result['total_time_ms']}ms) vượt ngưỡng nghiêm trọng "
                f"CRITICAL ({critical_threshold_ms}ms)."
            )
        elif result["total_time_ms"] >= warning_threshold_ms:
            result["is_degraded"] = True
            result["degradation_severity"] = "WARNING"
            result["degradation_reason"] = (
                f"Thời gian phản hồi ({result['total_time_ms']}ms) vượt ngưỡng cảnh báo "
                f"WARNING ({warning_threshold_ms}ms)."
            )

        # 2. Đánh giá suy giảm so với Baseline Lịch sử (Historical Baseline Comparison)
        if baseline_metrics:
            base_time = baseline_metrics.get("baseline_total_time_ms") or baseline_metrics.get("total_time_ms")
            if base_time and base_time > 0:
                diff_ms = result["total_time_ms"] - base_time
                ratio = diff_ms / base_time
                percent_change = round(ratio * 100, 2)

                comp = {
                    "baseline_total_time_ms": base_time,
                    "current_total_time_ms": result["total_time_ms"],
                    "diff_ms": round(diff_ms, 2),
                    "percent_change": percent_change,
                    "is_slower": diff_ms > 0
                }
                result["baseline_comparison"] = comp

                # Nếu tăng quá ngưỡng ratio (ví dụ > 50%) và chênh lệch tối thiểu 300ms
                if ratio >= DEFAULT_DEGRADATION_RATIO_THRESHOLD and diff_ms >= 300:
                    result["is_degraded"] = True
                    if result["degradation_severity"] == "HEALTHY":
                        result["degradation_severity"] = "WARNING"
                    reason_suffix = f"Hiệu năng chậm hơn {percent_change}% so với mốc baseline ({base_time}ms)."
                    if result["degradation_reason"]:
                        result["degradation_reason"] += f" | {reason_suffix}"
                    else:
                        result["degradation_reason"] = reason_suffix

    except Exception as e:
        result["error"] = str(e)
        result["is_degraded"] = True
        result["degradation_severity"] = "CRITICAL"
        result["performance_grade"] = "F (Error)"
        result["degradation_reason"] = f"Lỗi trong quá trình kiểm tra hiệu năng: {e}"

    return result

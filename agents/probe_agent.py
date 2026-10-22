"""
Probe Agent (Tác tử Thu thập Bằng chứng Kỹ thuật)
Chịu trách nhiệm thực thi các công cụ giám sát đa tín hiệu (HTTP, DNS, SSL, SRE, DOM, Visual),
chuẩn hóa kết quả đầu ra và ghi nhận bằng chứng thô phục vụ suy luận sự cố.

Tuân thủ kiến trúc phân tầng 2 lớp chuẩn SRE Enterprise:
- Tầng mạng song song (Layer 1 Probes): Kích hoạt đồng thời 3 công cụ (HTTP, DNS, SSL) qua đa luồng/bất đồng bộ.
- Tầng giao diện có điều kiện (Layer 2 Browser Probe): Chỉ khi tầng mạng xác nhận HTTP khả dụng (mã 2xx hoặc 3xx),
  mới kích hoạt trình duyệt không giao diện Playwright Chromium để kiểm tra DOM và Visual Regression.
"""

import time
import concurrent.futures
from typing import Dict, Any, Optional, List
from tools.http_checker import check_http
from tools.dns_checker import check_dns
from tools.ssl_checker import check_ssl
from tools.performance_checker import check_performance
from tools.dom_validator import validate_dom
from tools.visual_checker import check_visual_regression
from tools.tech_detector import detect_technology_stack

from config import (
    HTTP_TIMEOUT_SECONDS,
    DNS_TIMEOUT_SECONDS,
    SSL_TIMEOUT_SECONDS,
    PERFORMANCE_TIMEOUT_SECONDS,
    DOM_TIMEOUT_SECONDS,
    VISUAL_TIMEOUT_SECONDS
)

class ProbeAgent:
    """Tác tử điều động bộ công cụ và thu thập chứng cứ mạng."""

    def __init__(self, name: str = "Multi-Signal Probe Agent"):
        self.name = name

    def execute_probes(
        self,
        url: str,
        domain: str,
        expected_status: int = 200,
        baseline_dns: Optional[Dict[str, Any]] = None,
        probe_signals: Optional[List[str]] = None,
        capture_visual: bool = False,
        website_name: str = "Website"
    ) -> Dict[str, Any]:
        """
        Thực thi các công cụ giám sát phân tầng theo kiến trúc SRE tự hành:
        - Layer 1 (Mạng song song): Kích hoạt đồng thời HTTP, DNS, SSL siêu nhẹ.
        - Layer 2 (Trình duyệt có điều kiện): Kích hoạt DOM / Visual chỉ khi HTTP trả về 2xx/3xx.
        """
        if probe_signals is None:
            probe_signals = ["HTTP", "DNS", "SSL", "PERF", "DOM"]

        start_time = time.time()
        results: Dict[str, Any] = {
            "agent_name": self.name,
            "url": url,
            "domain": domain,
            "probes_executed": [],
            "evidence": {},
            "layer1_probes_parallel": True,
            "layer2_browser_conditional": True,
            "execution_time_ms": 0.0
        }

        # =========================================================================
        # TẦNG 1: TẦNG MẠNG SONG SONG (LAYER 1 PROBES - PARALLEL EXECUTION)
        # Kích hoạt đồng thời http_checker, dns_checker, ssl_checker
        # =========================================================================
        layer1_tasks = {}
        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
            if "HTTP" in probe_signals:
                layer1_tasks["http"] = executor.submit(
                    check_http, url=url, expected_status=expected_status, timeout=HTTP_TIMEOUT_SECONDS
                )
            if "DNS" in probe_signals:
                layer1_tasks["dns"] = executor.submit(
                    check_dns, domain=domain, baseline=baseline_dns, timeout=DNS_TIMEOUT_SECONDS
                )
            if "SSL" in probe_signals:
                layer1_tasks["ssl"] = executor.submit(
                    check_ssl, url_or_host=url, timeout=SSL_TIMEOUT_SECONDS
                )

            # Thu thập kết quả tầng 1
            for key, future in layer1_tasks.items():
                try:
                    res = future.result()
                    results["evidence"][key] = res
                    results["probes_executed"].append(f"{key}_checker")
                except Exception as ex:
                    results["evidence"][key] = {"error": str(ex), "status": "ERROR"}

        # 4. Tín hiệu Hiệu năng SRE (Resource Timing) qua Socket Timing siêu nhẹ
        if "PERF" in probe_signals:
            try:
                perf_res = check_performance(url=url, use_browser=False, timeout=PERFORMANCE_TIMEOUT_SECONDS)
                results["evidence"]["performance"] = perf_res
                results["probes_executed"].append("performance_checker")
            except Exception as ex:
                results["evidence"]["performance"] = {"error": str(ex), "status": "ERROR"}

        # =========================================================================
        # TẦNG 2: TẦNG GIAO DIỆN CÓ ĐIỀU KIỆN (LAYER 2 BROWSER PROBE - CONDITIONAL)
        # Chỉ khi tầng mạng xác nhận HTTP khả dụng (mã 2xx hoặc 3xx),
        # mới kích hoạt Playwright Chromium để thẩm định DOM và Visual Diff
        # =========================================================================
        http_res = results["evidence"].get("http", {})
        status_code = http_res.get("status_code")
        is_http_viable = (
            status_code is not None and (200 <= status_code < 400 or http_res.get("is_expected_status", False))
        )

        if is_http_viable:
            # 5. Tín hiệu Cấu trúc DOM (Structural Integrity) qua BS4 siêu nhanh
            if "DOM" in probe_signals:
                try:
                    dom_res = validate_dom(url=url, use_browser=False, timeout=DOM_TIMEOUT_SECONDS)
                    results["evidence"]["dom"] = dom_res
                    results["probes_executed"].append("dom_validator")
                except Exception as ex:
                    results["evidence"]["dom"] = {"error": str(ex), "status": "ERROR"}

            # 6. Tín hiệu Hình ảnh (Visual Regression qua Playwright - Full Page)
            if capture_visual or "VISUAL" in probe_signals:
                try:
                    visual_res = check_visual_regression(
                        url=url,
                        website_identifier=website_name,
                        full_page=True,
                        timeout=VISUAL_TIMEOUT_SECONDS
                    )
                    results["evidence"]["visual"] = visual_res
                    results["probes_executed"].append("visual_checker")
                except Exception as ex:
                    results["evidence"]["visual"] = {"error": str(ex), "status": "ERROR"}
        else:
            # Ghi nhận trạng thái bỏ qua tầng 2 do mạng không khả dụng theo thiết kế Section 3.2.2
            if "DOM" in probe_signals:
                results["evidence"]["dom"] = {
                    "can_inspect": False,
                    "is_structure_valid": True,
                    "bypassed": True,
                    "reason": f"Tầng mạng không khả dụng (HTTP {status_code or 'Failed'}). Bỏ qua kiểm tra DOM/Visual theo thiết kế Layer 2."
                }
            if capture_visual or "VISUAL" in probe_signals:
                results["evidence"]["visual"] = {
                    "can_inspect": False,
                    "bypassed": True,
                    "reason": f"Tầng mạng không khả dụng (HTTP {status_code or 'Failed'}). Bỏ qua kiểm tra DOM/Visual theo thiết kế Layer 2."
                }

        # =========================================================================
        # TẦNG 3: NHẬN DIỆN HỆ SINH THÁI CÔNG NGHỆ (TECH STACK FINGERPRINTING)
        # Tự động trích xuất Web Server, CDN/WAF, Ngôn ngữ, Framework/CMS & SRE Commands
        # =========================================================================
        try:
            tech_res = detect_technology_stack(
                url=url,
                http_res=results["evidence"].get("http"),
                dom_res=results["evidence"].get("dom")
            )
            results["evidence"]["tech_stack"] = tech_res
            results["probes_executed"].append("tech_detector")
        except Exception as ex:
            results["evidence"]["tech_stack"] = {"is_detected": False, "error": str(ex)}

        results["execution_time_ms"] = round((time.time() - start_time) * 1000, 2)
        return results

    def re_probe_specific_signal(
        self,
        signal: str,
        url: str,
        domain: str,
        expected_status: int = 200,
        baseline_dns: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Khả năng Self-Correction (Tự sửa sai): Kiểm tra lại tức thời 1 tín hiệu nghi ngờ để loại trừ lỗi chập chờn (Flapping).
        """
        if signal == "HTTP":
            return check_http(url=url, expected_status=expected_status, timeout=HTTP_TIMEOUT_SECONDS)
        elif signal == "DNS":
            return check_dns(domain=domain, baseline=baseline_dns, timeout=DNS_TIMEOUT_SECONDS)
        elif signal == "SSL":
            return check_ssl(url_or_host=url, timeout=SSL_TIMEOUT_SECONDS)
        elif signal == "PERF":
            return check_performance(url=url, timeout=PERFORMANCE_TIMEOUT_SECONDS)
        return {}

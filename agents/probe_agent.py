"""
Probe Agent (Tác tử Thu thập Bằng chứng Kỹ thuật)
Chịu trách nhiệm thực thi các công cụ giám sát đa tín hiệu (HTTP, DNS, SSL, SRE, DOM, Visual),
chuẩn hóa kết quả đầu ra và ghi nhận bằng chứng thô phục vụ suy luận sự cố.
"""

import time
from typing import Dict, Any, Optional, List
from tools.http_checker import check_http
from tools.dns_checker import check_dns
from tools.ssl_checker import check_ssl
from tools.performance_checker import check_performance
from tools.dom_validator import validate_dom
from tools.visual_checker import check_visual_regression

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

    def __init__(self, name: str = "Probe Agent"):
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
        Thực thi các công cụ giám sát theo danh sách tín hiệu được Orchestrator yêu cầu.
        Mặc định: ['HTTP', 'DNS', 'SSL'] và tùy chọn ['PERF', 'DOM', 'VISUAL'].
        """
        if probe_signals is None:
            probe_signals = ["HTTP", "DNS", "SSL"]

        start_time = time.time()
        results: Dict[str, Any] = {
            "agent_name": self.name,
            "url": url,
            "domain": domain,
            "probes_executed": [],
            "evidence": {},
            "execution_time_ms": 0.0
        }

        # 1. Tín hiệu HTTP
        if "HTTP" in probe_signals:
            http_res = check_http(url=url, expected_status=expected_status, timeout=HTTP_TIMEOUT_SECONDS)
            results["evidence"]["http"] = http_res
            results["probes_executed"].append("http_checker")

        # 2. Tín hiệu DNS
        if "DNS" in probe_signals:
            dns_res = check_dns(domain=domain, baseline=baseline_dns, timeout=DNS_TIMEOUT_SECONDS)
            results["evidence"]["dns"] = dns_res
            results["probes_executed"].append("dns_checker")

        # 3. Tín hiệu SSL/TLS
        if "SSL" in probe_signals:
            ssl_res = check_ssl(url_or_host=url, timeout=SSL_TIMEOUT_SECONDS)
            results["evidence"]["ssl"] = ssl_res
            results["probes_executed"].append("ssl_checker")

        # 4. Tín hiệu Hiệu năng SRE (Resource Timing)
        if "PERF" in probe_signals:
            try:
                perf_res = check_performance(url=url, timeout_seconds=PERFORMANCE_TIMEOUT_SECONDS)
                results["evidence"]["performance"] = perf_res
                results["probes_executed"].append("performance_checker")
            except Exception as ex:
                results["evidence"]["performance"] = {"error": str(ex), "status": "ERROR"}

        # 5. Tín hiệu Cấu trúc DOM (Structural Integrity)
        if "DOM" in probe_signals:
            try:
                dom_res = validate_dom(url=url, timeout_seconds=DOM_TIMEOUT_SECONDS)
                results["evidence"]["dom"] = dom_res
                results["probes_executed"].append("dom_validator")
            except Exception as ex:
                results["evidence"]["dom"] = {"error": str(ex), "status": "ERROR"}

        # 6. Tín hiệu Hình ảnh (Visual Regression qua Playwright)
        if capture_visual or "VISUAL" in probe_signals:
            try:
                visual_res = check_visual_regression(url=url, website_identifier=website_name, timeout=VISUAL_TIMEOUT_SECONDS)
                results["evidence"]["visual"] = visual_res
                results["probes_executed"].append("visual_checker")
            except Exception as ex:
                results["evidence"]["visual"] = {"error": str(ex), "status": "ERROR"}

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
        return {}

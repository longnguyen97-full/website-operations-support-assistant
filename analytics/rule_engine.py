from typing import Dict, Any, List, Optional
from config import SSL_EXPIRY_WARNING_DAYS, PERFORMANCE_WARNING_THRESHOLD_MS, PERFORMANCE_CRITICAL_THRESHOLD_MS, VISUAL_DIFF_THRESHOLD_PERCENT

class RuleBasedAnomalyEngine:
    """
    Bộ quy tắc đánh giá bất thường đa tín hiệu (Multi-Signal Rule Engine):
    Kiểm tra tính tuân thủ các quy tắc logic kỹ thuật trên từng tầng tín hiệu giám sát:
    - Tầng HTTP (RFC 9110)
    - Tầng DNS (RFC 1035)
    - Tầng SSL/TLS (RFC 5280 / RFC 8446)
    - Tầng Hiệu năng SRE (Performance SLAs)
    - Tầng Cấu trúc DOM (Structural Monitoring)
    - Tầng Giao diện Trực quan (Visual Regression)
    """

    def __init__(
        self,
        ssl_warning_days: int = SSL_EXPIRY_WARNING_DAYS,
        perf_warning_ms: float = PERFORMANCE_WARNING_THRESHOLD_MS,
        perf_critical_ms: float = PERFORMANCE_CRITICAL_THRESHOLD_MS,
        visual_diff_threshold: float = VISUAL_DIFF_THRESHOLD_PERCENT
    ):
        self.ssl_warning_days = ssl_warning_days
        self.perf_warning_ms = perf_warning_ms
        self.perf_critical_ms = perf_critical_ms
        self.visual_diff_threshold = visual_diff_threshold

    def evaluate_http_rules(self, http_res: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Đánh giá các luật bất thường tầng HTTP theo RFC 9110."""
        violations = []
        if not http_res:
            return violations

        status_code = http_res.get("status_code")
        is_expected = http_res.get("is_expected_status", False)
        error = http_res.get("error")
        error_type = http_res.get("error_type")

        # 1. Lỗi kết nối / Timeout HTTP
        if status_code is None or error:
            violations.append({
                "signal": "HTTP",
                "rule_id": "HTTP_CONN_FAILED",
                "severity": "CRITICAL",
                "title": http_res.get("error_title") or "Lỗi kết nối HTTP",
                "description": http_res.get("error_detail") or error or "Không thể thiết lập kết nối HTTP đến máy chủ.",
                "weight": 40
            })
            return violations

        # 2. Lỗi máy chủ (5xx Server Error)
        if 500 <= status_code <= 599:
            violations.append({
                "signal": "HTTP",
                "rule_id": "HTTP_5XX_SERVER_ERROR",
                "severity": "CRITICAL",
                "title": f"HTTP {status_code} Server Error",
                "description": f"Máy chủ gặp sự cố nội bộ hoặc không phản hồi kịp (HTTP {status_code}).",
                "weight": 35
            })

        # 3. Lỗi client (4xx Client Error) - nếu không phải expected
        elif 400 <= status_code <= 499 and not is_expected:
            violations.append({
                "signal": "HTTP",
                "rule_id": "HTTP_4XX_CLIENT_ERROR",
                "severity": "WARNING",
                "title": f"HTTP {status_code} Client Error",
                "description": f"Yêu cầu không hợp lệ hoặc tài nguyên không tìm thấy (HTTP {status_code}).",
                "weight": 20
            })

        # 4. Sai lệch mã trạng thái kỳ vọng (Status Mismatch)
        elif not is_expected:
            violations.append({
                "signal": "HTTP",
                "rule_id": "HTTP_STATUS_MISMATCH",
                "severity": "WARNING",
                "title": "Sai lệch Mã trạng thái HTTP kỳ vọng",
                "description": f"Nhận được HTTP {status_code} trong khi mốc chuẩn mong đợi là {http_res.get('expected_status')}.",
                "weight": 15
            })

        # 5. Vòng lặp chuyển hướng (Redirect Loop / Long chain)
        redirects = http_res.get("redirect_chain", [])
        if len(redirects) > 4:
            violations.append({
                "signal": "HTTP",
                "rule_id": "HTTP_EXCESSIVE_REDIRECTS",
                "severity": "WARNING",
                "title": "Chuỗi chuyển hướng (Redirect Chain) quá dài",
                "description": f"Phát hiện {len(redirects)} bước chuyển hướng liên tiếp.",
                "weight": 10
            })

        return violations

    def evaluate_dns_rules(self, dns_res: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Đánh giá các luật bất thường tầng DNS theo RFC 1035."""
        violations = []
        if not dns_res:
            return violations

        resolved = dns_res.get("resolved", False)
        error = dns_res.get("error")

        # 1. Thất bại hoàn toàn phân giải DNS
        if not resolved:
            violations.append({
                "signal": "DNS",
                "rule_id": "DNS_RESOLUTION_FAILED",
                "severity": "CRITICAL",
                "title": dns_res.get("error_title") or "Lỗi Phân giải Tên miền (DNS Failure)",
                "description": dns_res.get("error_detail") or error or "Không thể phân giải tên miền thành địa chỉ IP.",
                "weight": 40
            })
            return violations

        # 2. Sai lệch bản ghi so với Baseline (DNS Drift - Không phải Load Balancing)
        changes = dns_res.get("changes_detected", {})
        is_lb = dns_res.get("is_load_balancing_suspected", False)
        if changes and not is_lb:
            violations.append({
                "signal": "DNS",
                "rule_id": "DNS_UNEXPECTED_DRIFT",
                "severity": "WARNING",
                "title": "Phát hiện Biến đổi Bản ghi DNS ngoài dự kiến",
                "description": f"Các bản ghi DNS ({', '.join(changes.keys())}) đã thay đổi so với mốc baseline chuẩn.",
                "weight": 20
            })

        return violations

    def evaluate_ssl_rules(self, ssl_res: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Đánh giá các luật bất thường chứng chỉ SSL/TLS theo RFC 5280 / RFC 8446."""
        violations = []
        if not ssl_res:
            return violations

        # Khi website chạy HTTP thuần hoặc socket không kết nối được (do máy chủ down), bỏ qua lỗi SSL để tránh báo động giả
        if ssl_res.get("is_http_only") or ssl_res.get("can_connect") is False:
            return violations

        is_valid = ssl_res.get("is_valid", False)
        days = ssl_res.get("days_remaining", 0)
        is_expired = ssl_res.get("is_expired", False)
        is_self_signed = ssl_res.get("is_self_signed", False)
        is_untrusted_ca = ssl_res.get("is_untrusted_ca", False)
        hostname_matched = ssl_res.get("hostname_matched", False)

        # 1. Chứng chỉ hết hạn
        if is_expired or days < 0:
            violations.append({
                "signal": "SSL",
                "rule_id": "SSL_CERTIFICATE_EXPIRED",
                "severity": "CRITICAL",
                "title": "Chứng chỉ SSL/TLS đã Hết Hạn",
                "description": f"Chứng chỉ bảo mật đã hết hạn (quá {abs(days)} ngày), trình duyệt người dùng sẽ chặn truy cập.",
                "weight": 35
            })

        # 2. Sai lệch Hostname (Hostname Mismatch)
        elif not hostname_matched:
            violations.append({
                "signal": "SSL",
                "rule_id": "SSL_HOSTNAME_MISMATCH",
                "severity": "CRITICAL",
                "title": "Sai lệch Tên miền Chứng chỉ (Hostname Mismatch)",
                "description": f"Chứng chỉ SSL không cấp cho domain '{ssl_res.get('hostname')}'.",
                "weight": 30
            })

        # 3. Chứng chỉ tự ký (Self-signed) hoặc Không được CA tin cậy (Broken chain)
        elif (is_self_signed or is_untrusted_ca) and not (hostname.endswith(".test") or hostname.endswith(".local") or hostname == "localhost"):
            violations.append({
                "signal": "SSL",
                "rule_id": "SSL_UNTRUSTED_CA",
                "severity": "CRITICAL",
                "title": "Chứng chỉ Tự Ký hoặc Chuỗi Chứng chỉ Không Hợp Lệ",
                "description": "Tổ chức phát hành (CA) không nằm trong danh sách tin cậy hoặc chuỗi trung gian bị thiếu.",
                "weight": 25
            })

        # 4. Chứng chỉ sắp hết hạn trong ngưỡng cảnh báo
        elif days <= self.ssl_warning_days:
            violations.append({
                "signal": "SSL",
                "rule_id": "SSL_EXPIRING_SOON",
                "severity": "WARNING",
                "title": "Chứng chỉ SSL/TLS Sắp Hết Hạn",
                "description": f"Chứng chỉ chỉ còn {days} ngày hiệu lực (ngưỡng cảnh báo: <= {self.ssl_warning_days} ngày).",
                "weight": 15
            })

        # 5. Lỗi xác thực SSL chung khác
        elif not is_valid:
            violations.append({
                "signal": "SSL",
                "rule_id": "SSL_INVALID_UNKNOWN",
                "severity": "CRITICAL",
                "title": ssl_res.get("error_title") or "Lỗi Chứng chỉ SSL/TLS",
                "description": ssl_res.get("error_detail") or ssl_res.get("error") or "Chứng chỉ không hợp lệ.",
                "weight": 25
            })

        return violations

    def evaluate_performance_rules(self, perf_res: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Đánh giá các luật hiệu năng theo chuẩn SRE SLA."""
        violations = []
        if not perf_res:
            return violations

        total_time = perf_res.get("total_time_ms", 0.0)
        is_degraded = perf_res.get("is_degraded", False)
        reason = perf_res.get("degradation_reason")

        if total_time >= self.perf_critical_ms:
            violations.append({
                "signal": "PERFORMANCE",
                "rule_id": "PERF_CRITICAL_LATENCY",
                "severity": "CRITICAL",
                "title": f"Độ trễ Vượt Ngưỡng Nghiêm Trọng ({total_time}ms)",
                "description": f"Thời gian phản hồi {total_time}ms vượt quá ngưỡng SLA cho phép ({self.perf_critical_ms}ms).",
                "weight": 30
            })
        elif total_time >= self.perf_warning_ms or is_degraded:
            violations.append({
                "signal": "PERFORMANCE",
                "rule_id": "PERF_DEGRADED_LATENCY",
                "severity": "WARNING",
                "title": f"Hiệu năng Suy Giảm ({total_time}ms)",
                "description": reason or f"Thời gian phản hồi {total_time}ms vượt ngưỡng cảnh báo ({self.perf_warning_ms}ms).",
                "weight": 15
            })

        return violations

    def evaluate_dom_rules(self, dom_res: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Đánh giá các luật bất thường cấu trúc DOM."""
        violations = []
        if not dom_res:
            return violations

        if not dom_res.get("is_structure_valid", True):
            missing = dom_res.get("missing_critical_elements", [])
            anomalies = dom_res.get("structural_anomalies", [])
            violations.append({
                "signal": "DOM",
                "rule_id": "DOM_STRUCTURAL_CORRUPTION",
                "severity": "CRITICAL" if "Body Content" in missing else "WARNING",
                "title": "Bất thường Cấu trúc Trang Web (DOM Anomaly)",
                "description": f"Thiếu các thành phần cốt lõi: {', '.join(missing or anomalies)}",
                "weight": 25
            })

        return violations

    def evaluate_visual_rules(self, visual_res: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Đánh giá các luật chênh lệch giao diện người dùng (Visual Regression)."""
        violations = []
        if not visual_res:
            return violations

        if visual_res.get("is_regression_detected"):
            diff_pct = visual_res.get("diff_percentage", 0.0)
            violations.append({
                "signal": "VISUAL",
                "rule_id": "VISUAL_REGRESSION_DETECTED",
                "severity": "CRITICAL" if diff_pct >= 10.0 else "WARNING",
                "title": f"Phát hiện Biến Dạng Giao Diện ({diff_pct}%)",
                "description": f"Chênh lệch pixel giao diện so với baseline đạt {diff_pct}% (ngưỡng cho phép: <= {self.visual_diff_threshold}%).",
                "weight": 25
            })

        return violations

    def evaluate_all_rules(
        self,
        http_res: Optional[Dict[str, Any]] = None,
        dns_res: Optional[Dict[str, Any]] = None,
        ssl_res: Optional[Dict[str, Any]] = None,
        perf_res: Optional[Dict[str, Any]] = None,
        dom_res: Optional[Dict[str, Any]] = None,
        visual_res: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """Chạy đồng thời toàn bộ các luật quy tắc trên các tín hiệu."""
        all_violations = []
        if http_res:
            all_violations.extend(self.evaluate_http_rules(http_res))
        if dns_res:
            all_violations.extend(self.evaluate_dns_rules(dns_res))
        if ssl_res:
            all_violations.extend(self.evaluate_ssl_rules(ssl_res))
        if perf_res:
            all_violations.extend(self.evaluate_performance_rules(perf_res))
        if dom_res:
            all_violations.extend(self.evaluate_dom_rules(dom_res))
        if visual_res:
            all_violations.extend(self.evaluate_visual_rules(visual_res))
        return all_violations

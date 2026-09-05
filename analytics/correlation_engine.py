from typing import List, Dict, Any, Optional

class RuleBasedCorrelationEngine:
    """
    Bộ tương quan sự cố dựa trên luật (Rule-Based Incident Correlation Engine):
    Nhóm các cảnh báo rời rạc từ đa tín hiệu (HTTP, DNS, SSL, Perf, DOM, Visual) thành 1 sự cố duy nhất,
    triệt tiêu cảnh báo trùng lặp/báo động giả (Noise Reduction) mà không cần dùng LLM Agent.
    """

    @staticmethod
    def correlate_violations(violations: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Tương quan các vi phạm luật và suy luận nguyên nhân gốc sơ bộ:
        """
        if not violations:
            return {
                "has_incident": False,
                "incident_type": "NO_INCIDENT",
                "root_cause_summary": "Hệ thống hoạt động bình thường, không ghi nhận sự cố.",
                "overall_severity": "HEALTHY",
                "suppressed_alerts_count": 0,
                "primary_issue": None,
                "correlated_signals": []
            }

        rule_ids = {v["rule_id"] for v in violations}
        severities = {v["severity"] for v in violations}
        overall_severity = "CRITICAL" if "CRITICAL" in severities else ("WARNING" if "WARNING" in severities else "HEALTHY")

        primary_issue = None
        incident_type = "UNKNOWN_INCIDENT"
        root_cause = ""
        suppressed_count = 0

        # Pattern 1: DNS Failure (Nguyên nhân gốc cao nhất của hạ tầng mạng)
        if "DNS_RESOLUTION_FAILED" in rule_ids:
            incident_type = "DNS_FAILURE"
            primary_issue = next(v for v in violations if v["rule_id"] == "DNS_RESOLUTION_FAILED")
            root_cause = "Sự cố phân giải DNS: Không thể tìm thấy địa chỉ IP máy chủ (gây gián đoạn toàn bộ tầng HTTP và SSL phía sau)."
            # Triệt tiêu các lỗi HTTP connection / SSL handshake do DNS gây ra
            suppressed_count = len([v for v in violations if v["signal"] in ["HTTP", "SSL"]])

        # Pattern 2: Redirect Loop (Lớp điều hướng HTTP L7)
        elif "HTTP_REDIRECT_LOOP_DETECTED" in rule_ids or "HTTP_EXCESSIVE_REDIRECTS" in rule_ids:
            incident_type = "REDIRECT_LOOP"
            primary_issue = next((v for v in violations if v["rule_id"] in ["HTTP_REDIRECT_LOOP_DETECTED", "HTTP_EXCESSIVE_REDIRECTS"]), violations[0])
            root_cause = "Vòng lặp chuyển hướng vô hạn (Redirect Loop): Cấu hình chuyển tiếp HTTP 301/302 đệ quy khiến trình duyệt không thể tải trang đích."
            suppressed_count = max(0, len(violations) - 1)

        # Pattern 3: Server Down / Connection Refused (Hạ tầng L4 Socket & 502/503/504)
        elif "HTTP_CONN_FAILED" in rule_ids or "HTTP_5XX_SERVER_DOWN" in rule_ids:
            primary_issue = next((v for v in violations if v["rule_id"] in ["HTTP_CONN_FAILED", "HTTP_5XX_SERVER_DOWN"]), violations[0])
            err_text = str(primary_issue.get("description", "")).lower()
            if "redirect" in err_text or "toomanyredirects" in err_text:
                incident_type = "REDIRECT_LOOP"
                root_cause = "Vòng lặp chuyển hướng vô hạn (Redirect Loop): Máy chủ trả về HTTP 301/302 chuyển tiếp đệ quy không thể tải trang."
            elif "timeout" in err_text:
                incident_type = "HIGH_LATENCY"
                root_cause = "Yêu cầu kết nối mạng bị Timeout: Máy chủ quá tải hoặc độ trễ phản hồi vượt ngưỡng."
            elif "refused" in err_text or "10061" in err_text or "actively refused" in err_text:
                incident_type = "SERVER_DOWN"
                root_cause = "Máy chủ từ chối kết nối (Connection Refused): Dịch vụ web (Nginx/Apache/App Server) đang bị tắt hoặc Port đóng."
            else:
                incident_type = "SERVER_DOWN"
                root_cause = f"Dịch vụ máy chủ ngưng hoạt động hoặc reverse proxy không kết nối được upstream ({primary_issue.get('title')})."
            suppressed_count = len([v for v in violations if v["rule_id"] != primary_issue["rule_id"]])

        # Pattern 4: SSL/TLS Certificate Issues (Lớp bảo mật L6)
        elif "SSL_CERTIFICATE_EXPIRED" in rule_ids:
            incident_type = "SSL_EXPIRED"
            primary_issue = next(v for v in violations if v["rule_id"] == "SSL_CERTIFICATE_EXPIRED")
            root_cause = "Chứng chỉ số SSL/TLS đã hết hạn: Trình duyệt người dùng sẽ hiện cảnh báo bảo mật và từ chối truy cập."
            suppressed_count = len(violations) - 1

        elif "SSL_HOSTNAME_MISMATCH" in rule_ids or "SSL_UNTRUSTED_CA" in rule_ids:
            incident_type = "SSL_INVALID"
            primary_issue = next(v for v in violations if v["rule_id"] in ["SSL_HOSTNAME_MISMATCH", "SSL_UNTRUSTED_CA"])
            if primary_issue["rule_id"] == "SSL_HOSTNAME_MISMATCH":
                root_cause = "Chứng chỉ SSL không hợp lệ cho tên miền này (Hostname Mismatch)."
            else:
                root_cause = "Chứng chỉ SSL tự ký hoặc thiếu Intermediate CA trong chuỗi chứng chỉ (Untrusted CA)."
            suppressed_count = len(violations) - 1

        # Pattern 5: HTTP 500 Backend Application Exception Error
        elif "HTTP_500_INTERNAL_ERROR" in rule_ids or "HTTP_5XX_SERVER_ERROR" in rule_ids:
            incident_type = "BACKEND_500"
            primary_issue = next(v for v in violations if v["rule_id"] in ["HTTP_500_INTERNAL_ERROR", "HTTP_5XX_SERVER_ERROR"])
            root_cause = f"Lỗi phía Backend/Server ({primary_issue.get('title')}): Ứng dụng gặp Exception nội bộ hoặc Database không phản hồi."
            suppressed_count = len(violations) - 1

        # Pattern 6: Performance Spike / Degradation (Độ trễ cao / Timeout)
        elif "PERF_CRITICAL_LATENCY" in rule_ids or "PERF_DEGRADED_LATENCY" in rule_ids or "HTTP_TIMEOUT_ERROR" in rule_ids or "STAT_Z_SCORE_SPIKE" in rule_ids:
            incident_type = "HIGH_LATENCY"
            primary_issue = next((v for v in violations if v["rule_id"] in ["PERF_CRITICAL_LATENCY", "PERF_DEGRADED_LATENCY", "HTTP_TIMEOUT_ERROR", "STAT_Z_SCORE_SPIKE"]), violations[0])
            root_cause = f"Suy giảm hiệu năng hệ thống hoặc độ trễ phản hồi vượt ngưỡng: {primary_issue.get('description')}."
            suppressed_count = max(0, len(violations) - 1)

        # Pattern 7: Visual / DOM Deformation
        elif "VISUAL_REGRESSION_DETECTED" in rule_ids or "DOM_STRUCTURAL_CORRUPTION" in rule_ids:
            incident_type = "MISSING_DOM"
            primary_issue = next((v for v in violations if v["rule_id"] in ["VISUAL_REGRESSION_DETECTED", "DOM_STRUCTURAL_CORRUPTION"]), violations[0])
            root_cause = f"Biến dạng giao diện hoặc lỗi cấu trúc DOM: {primary_issue.get('description')}."
            suppressed_count = max(0, len(violations) - 1)

        # Fallback default:
        else:
            primary_issue = violations[0]
            incident_type = primary_issue.get("rule_id", "GENERAL_ANOMALY")
            root_cause = primary_issue.get("description") or primary_issue.get("title")

        return {
            "has_incident": True,
            "incident_type": incident_type,
            "root_cause_summary": root_cause,
            "overall_severity": overall_severity,
            "primary_issue": primary_issue,
            "raw_violations_count": len(violations),
            "suppressed_alerts_count": max(0, suppressed_count),
            "correlated_signals": list({v["signal"] for v in violations}),
            "all_violations": violations
        }

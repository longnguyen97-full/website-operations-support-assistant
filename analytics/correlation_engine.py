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
            incident_type = "DNS_RESOLUTION_OUTAGE"
            primary_issue = next(v for v in violations if v["rule_id"] == "DNS_RESOLUTION_FAILED")
            root_cause = "Sự cố phân giải DNS: Không thể tìm thấy địa chỉ IP máy chủ (gây gián đoạn toàn bộ tầng HTTP và SSL phía sau)."
            # Triệt tiêu các lỗi HTTP connection / SSL handshake do DNS gây ra
            suppressed_count = len([v for v in violations if v["signal"] in ["HTTP", "SSL"]])

        # Pattern 2: Server Down / Connection Refused (Hạ tầng L4 Socket)
        elif "HTTP_CONN_FAILED" in rule_ids:
            primary_issue = next(v for v in violations if v["rule_id"] == "HTTP_CONN_FAILED")
            err_text = str(primary_issue.get("description", "")).lower()
            if "refused" in err_text or "10061" in err_text or "actively refused" in err_text:
                incident_type = "SERVER_PROCESS_DOWN"
                root_cause = "Máy chủ từ chối kết nối (Connection Refused): Dịch vụ web (Nginx/Apache/App Server) đang bị tắt hoặc Port đóng."
            elif "timeout" in err_text:
                incident_type = "NETWORK_GATEWAY_TIMEOUT"
                root_cause = "Yêu cầu kết nối mạng bị Timeout: Máy chủ quá tải hoặc tường lửa (Firewall) chặn gói tin."
            else:
                incident_type = "HTTP_CONNECTIVITY_OUTAGE"
                root_cause = f"Gián đoạn kết nối HTTP: {primary_issue.get('title')}."
            suppressed_count = len([v for v in violations if v["rule_id"] != primary_issue["rule_id"]])

        # Pattern 3: SSL/TLS Certificate Issues (Lớp bảo mật L6)
        elif "SSL_CERTIFICATE_EXPIRED" in rule_ids:
            incident_type = "SSL_CERT_EXPIRED"
            primary_issue = next(v for v in violations if v["rule_id"] == "SSL_CERTIFICATE_EXPIRED")
            root_cause = "Chứng chỉ số SSL/TLS đã hết hạn: Trình duyệt người dùng sẽ hiện cảnh báo bảo mật và từ chối truy cập."
            suppressed_count = len(violations) - 1

        elif "SSL_HOSTNAME_MISMATCH" in rule_ids:
            incident_type = "SSL_HOSTNAME_MISMATCH"
            primary_issue = next(v for v in violations if v["rule_id"] == "SSL_HOSTNAME_MISMATCH")
            root_cause = "Chứng chỉ SSL không hợp lệ cho tên miền này (Hostname Mismatch)."
            suppressed_count = len(violations) - 1

        elif "SSL_UNTRUSTED_CA" in rule_ids:
            incident_type = "SSL_UNTRUSTED_CA"
            primary_issue = next(v for v in violations if v["rule_id"] == "SSL_UNTRUSTED_CA")
            root_cause = "Chứng chỉ SSL tự ký hoặc thiếu Intermediate CA trong chuỗi chứng chỉ."
            suppressed_count = len(violations) - 1

        # Pattern 4: 5xx Backend Application Server Error
        elif "HTTP_5XX_SERVER_ERROR" in rule_ids:
            incident_type = "BACKEND_APPLICATION_ERROR"
            primary_issue = next(v for v in violations if v["rule_id"] == "HTTP_5XX_SERVER_ERROR")
            root_cause = f"Lỗi phía Backend/Server ({primary_issue.get('title')}): Ứng dụng gặp Exception nội bộ hoặc Database không phản hồi."
            suppressed_count = len(violations) - 1

        # Pattern 5: Performance Spike / Degradation (Độ trễ cao đơn thuần)
        elif "PERF_CRITICAL_LATENCY" in rule_ids or "PERF_DEGRADED_LATENCY" in rule_ids:
            incident_type = "PERFORMANCE_DEGRADATION"
            primary_issue = next((v for v in violations if v["rule_id"] in ["PERF_CRITICAL_LATENCY", "PERF_DEGRADED_LATENCY"]), violations[0])
            root_cause = f"Suy giảm hiệu năng hệ thống: {primary_issue.get('description')}."
            suppressed_count = max(0, len(violations) - 1)

        # Pattern 6: Visual / DOM Deformation
        elif "VISUAL_REGRESSION_DETECTED" in rule_ids or "DOM_STRUCTURAL_CORRUPTION" in rule_ids:
            incident_type = "FRONTEND_UI_DEFORMATION"
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

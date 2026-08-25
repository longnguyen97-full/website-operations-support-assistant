"""
Reporting and Notification Agent (Tác tử Báo cáo & Phân phối Cảnh báo)
Chịu trách nhiệm tổng hợp kết quả phân tích từ các tác tử trước, sinh định dạng cảnh báo chuẩn hóa
và phân phối thông báo qua Email SMTP hoặc Webhook.
"""

from typing import Dict, Any, Optional
from notifications.email_service import check_and_send_alert

class ReportingNotificationAgent:
    """Tác tử tạo lập báo cáo và gửi thông báo cảnh báo."""

    def __init__(self, name: str = "Reporting and Notification Agent"):
        self.name = name

    def generate_and_dispatch(
        self,
        website_info: Dict[str, Any],
        analysis_result: Dict[str, Any],
        evidence_data: Dict[str, Any],
        overall_severity: str = "HEALTHY"
    ) -> Dict[str, Any]:
        """
        Định dạng báo cáo sự cố và kích hoạt cơ chế gửi cảnh báo Email/Webhook.
        """
        http_res = evidence_data.get("http", {})
        dns_res = evidence_data.get("dns", {})
        ssl_res = evidence_data.get("ssl", {})

        # Gửi cảnh báo qua Email nếu có sự cố và cấu hình email được bật
        email_dispatched = False
        try:
            email_dispatched = check_and_send_alert(
                site=website_info,
                overall_status=overall_severity,
                http_res=http_res,
                dns_res=dns_res,
                ssl_res=ssl_res
            )
        except Exception:
            email_dispatched = False

        # Chuẩn hóa Report Digest
        report_digest = {
            "agent_name": self.name,
            "website_name": website_info.get("name"),
            "url": website_info.get("url"),
            "severity": overall_severity,
            "title": analysis_result.get("incident_title", "Báo cáo Giám sát Định kỳ"),
            "summary": analysis_result.get("executive_summary"),
            "root_cause": analysis_result.get("root_cause"),
            "action_plan": analysis_result.get("action_plan", []),
            "email_dispatched": email_dispatched,
            "rfc_citations": analysis_result.get("rfc_citations", [])
        }

        return report_digest

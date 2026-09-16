"""
Reporting and Notification Agent (Tác tử Báo cáo & Phân phối Cảnh báo)
Chịu trách nhiệm tổng hợp kết quả phân tích từ các tác tử trước, sinh định dạng cảnh báo chuẩn hóa
và phân phối thông báo qua Email SMTP hoặc Webhook.
"""

from typing import Dict, Any, Optional
from notifications.email_service import check_and_send_alert, get_last_dispatch_result

class ReportingNotificationAgent:
    """Tác tử tạo lập báo cáo và gửi thông báo cảnh báo."""

    def __init__(self, name: str = "Reporting and Notification Agent"):
        self.name = name

    def generate_and_dispatch(
        self,
        website_info: Dict[str, Any],
        analysis_result: Dict[str, Any],
        evidence_data: Dict[str, Any],
        overall_severity: str = "HEALTHY",
        dispatch_alert: bool = True
    ) -> Dict[str, Any]:
        """
        Định dạng báo cáo sự cố toàn diện 8 phần và kích hoạt cơ chế gửi cảnh báo Email/Webhook (nếu được cho phép).
        """
        http_res = evidence_data.get("http", {})
        dns_res = evidence_data.get("dns", {})
        ssl_res = evidence_data.get("ssl", {})

        # Gửi cảnh báo qua Email nếu được cho phép và phát hiện sự cố (CRITICAL / WARNING)
        email_dispatched = False
        dispatch_msg = ""
        if dispatch_alert and overall_severity in ["CRITICAL", "WARNING"]:
            try:
                email_dispatched = bool(check_and_send_alert(
                    site=website_info,
                    overall_status=overall_severity,
                    http_res=http_res,
                    dns_res=dns_res,
                    ssl_res=ssl_res,
                    force_send=True,
                    rca_report=analysis_result
                ))
                dispatch_msg = get_last_dispatch_result().get("message", "")
            except Exception as e:
                print(f"[!] ReportingNotificationAgent: Lỗi gửi email cảnh báo: {e}")
                email_dispatched = False
                dispatch_msg = str(e)
        else:
            email_dispatched = False
            dispatch_msg = "Không kích hoạt gửi cảnh báo."

        # Chuẩn hóa Report Digest toàn diện
        report_digest = {
            "agent_name": self.name,
            "website_name": website_info.get("name"),
            "url": website_info.get("url"),
            "severity": overall_severity,
            "incident_id": analysis_result.get("incident_id"),
            "timestamp": analysis_result.get("timestamp"),
            "fault_layer": analysis_result.get("fault_layer"),
            "confidence_score": analysis_result.get("confidence_score", 95.0),
            "title": analysis_result.get("incident_title", "Báo cáo Giám sát Định kỳ"),
            "summary": analysis_result.get("executive_summary"),
            "root_cause": analysis_result.get("root_cause_analysis", {}).get("primary_cause"),
            "action_plan": analysis_result.get("immediate_action_plan", []),
            "investigation_runbook": analysis_result.get("investigation_runbook", []),
            "prevention_strategy": analysis_result.get("prevention_strategy", []),
            "rfc_citations": analysis_result.get("technical_standards", []),
            "email_dispatched": email_dispatched,
            "dispatch_message": dispatch_msg,
            "full_rca_report": analysis_result
        }

        return report_digest

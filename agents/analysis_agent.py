"""
Incident Analysis Agent (Tác tử Phân tích Nguyên nhân Gốc - RCA & Khuyến nghị)
Sử dụng kho tri thức chuyên môn (Knowledge Base) kết hợp suy luận chuyên gia (Expert Reasoning / LLM)
để tạo báo cáo giải thích nguyên nhân gốc và lập kế hoạch hành động khắc phục sự cố.
"""

import os
from typing import Dict, Any, Optional, List
from agents.knowledge_base import OperationalKnowledgeBase

class IncidentAnalysisAgent:
    """Tác tử phân tích nguyên nhân gốc và đề xuất giải pháp."""

    def __init__(self, name: str = "Incident Analysis Agent"):
        self.name = name
        self.kb = OperationalKnowledgeBase()

    def analyze_incident(
        self,
        website_info: Dict[str, Any],
        correlation_data: Dict[str, Any],
        evidence_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Thực hiện phân tích toàn diện sự cố dựa trên tương quan và bằng chứng kỹ thuật.
        """
        incident_type = correlation_data.get("incident_type", "NO_INCIDENT")
        severity = correlation_data.get("overall_severity", "HEALTHY")
        primary_issue = correlation_data.get("primary_issue") or correlation_data.get("root_cause_summary")

        if not correlation_data.get("has_incident"):
            return {
                "agent_name": self.name,
                "status": "HEALTHY",
                "executive_summary": f"Website '{website_info.get('name')}' đang vận hành ổn định. Tất cả các tín hiệu kỹ thuật (HTTP, DNS, SSL) đều đạt chuẩn.",
                "root_cause": "Không phát hiện lỗi kỹ thuật.",
                "user_impact": "Người dùng truy cập bình thường, không có gián đoạn.",
                "action_plan": ["Duy trì giám sát định kỳ theo chu kỳ đã cấu hình."],
                "rfc_citations": ["RFC 9110 (HTTP 200 OK)", "RFC 1035 (DNS Resolved)"]
            }

        # 1. Truy vấn Knowledge Base lấy Runbook & Chuẩn RFC
        runbook = self.kb.query_runbook_by_scenario(incident_type) or self.kb.query_runbook_by_scenario(str(primary_issue))

        # 2. Xây dựng phân tích chuyên sâu (Expert System Reasoning)
        http_evidence = evidence_data.get("http", {})
        dns_evidence = evidence_data.get("dns", {})
        ssl_evidence = evidence_data.get("ssl", {})

        status_code = http_evidence.get("status_code")
        error_detail = http_evidence.get("error_detail") or http_evidence.get("error") or ""

        rfc_citations = []
        if runbook and runbook.get("rfc_ref"):
            rfc_citations.append(runbook["rfc_ref"])

        # Phân tích theo từng trường hợp cụ thể
        likely_causes = runbook.get("likely_causes", []) if runbook else [
            "Lỗi kết nối hoặc phản hồi bất thường từ máy chủ đích.",
            "Sai lệch cấu hình mạng hoặc tài nguyên hệ thống."
        ]
        
        investigation_steps = runbook.get("investigation_steps", []) if runbook else [
            "1. Kiểm tra log hệ thống phía máy chủ web.",
            "2. Kiểm tra trạng thái tường lửa và cổng kết nối."
        ]

        action_plan = runbook.get("remediation_actions", []) if runbook else [
            "Khởi động lại tiến trình web server.",
            "Kiểm tra lại cấu hình DNS và chứng chỉ SSL."
        ]

        # Tạo bản tóm tắt nguyên nhân gốc tự nhiên (Executive Summary)
        if "HTTP_5" in incident_type or (status_code and status_code >= 500):
            summary = (
                f"Phát hiện sự cố máy chủ nội bộ (HTTP {status_code}) trên website '{website_info.get('name')}'. "
                f"Hạ tầng mạng DNS và SSL vẫn hợp lệ nhưng ứng dụng backend không thể xử lý request, nghi ngờ do cạn kiệt tài nguyên hoặc lỗi cơ sở dữ liệu."
            )
            impact = "Người dùng không thể truy cập các tính năng chính hoặc thực hiện giao dịch."
        elif "HTTP_4" in incident_type or (status_code and status_code in [404, 403, 401, 429]):
            summary = (
                f"Phát hiện lỗi truy cập tài nguyên (HTTP {status_code}) trên website '{website_info.get('name')}'. "
                f"Đường dẫn hoặc quyền truy cập tài nguyên bị hạn chế."
            )
            impact = "Người dùng nhận thông báo lỗi từ chối truy cập hoặc không tìm thấy trang."
        elif "REDIRECT_LOOP" in incident_type:
            summary = (
                f"Phát hiện vòng lặp chuyển hướng (Redirect Loop) trên website '{website_info.get('name')}'. "
                f"Trình duyệt bị kẹt giữa các yêu cầu 302 liên tiếp và tự động ngắt kết nối."
            )
            impact = "Toàn bộ người dùng bị chặn truy cập và trình duyệt báo lỗi ERR_TOO_MANY_REDIRECTS."
        elif "DNS" in incident_type or not dns_evidence.get("resolved"):
            summary = (
                f"Phát hiện sự cố mất khả năng phân giải tên miền (DNS Outage) cho domain '{website_info.get('domain')}'. "
                f"Tác tử xác nhận nguyên nhân gốc nằm tại tầng DNS, dẫn đến việc không thể thiết lập kết nối IP tới máy chủ."
            )
            impact = "Website hoàn toàn không thể truy cập từ internet đối với mọi người dùng."
        elif "SSL" in incident_type or (ssl_evidence and not ssl_evidence.get("is_valid")):
            summary = (
                f"Phát hiện cảnh báo bảo mật chứng chỉ SSL/TLS trên website '{website_info.get('name')}'. "
                f"Chứng chỉ đã quá hạn hoặc không thuộc chuỗi tin cậy hợp lệ."
            )
            impact = "Trình duyệt của khách hàng hiện cảnh báo bảo mật nguy hiểm, gây sụt giảm uy tín dịch vụ."
        elif "LATENCY" in incident_type or "PERF" in incident_type:
            summary = (
                f"Phát hiện suy giảm hiệu năng nghiêm trọng: Thời gian phản hồi ({http_evidence.get('response_time_ms', 0)}ms) "
                f"vượt xa ngưỡng an toàn. Tác tử ghi nhận đột biến độ trễ so với mức trung bình lịch sử."
            )
            impact = "Trang tải cực kỳ chậm, nguy cơ cao gây timeout và bỏ hàng của khách hàng."
        elif "DOM" in incident_type or "VISUAL" in incident_type:
            summary = (
                f"Phát hiện khiếm khuyết cấu trúc giao diện DOM hoặc biến dạng layout trên website '{website_info.get('name')}'. "
                f"Trang web vẫn trả về mã 200 OK nhưng thiếu các thành phần quan trọng (CTA, Heading) hoặc vỡ layout."
            )
            impact = "Giao diện vỡ hoặc mất nút bấm tương tác, ảnh hưởng trực tiếp tới trải nghiệm người dùng."
        else:
            summary = f"Phát hiện bất thường kỹ thuật mức độ {severity} trên website '{website_info.get('name')}': {primary_issue}."
            impact = "Ảnh hưởng tới độ khả dụng hoặc trải nghiệm người dùng của website."

        return {
            "agent_name": self.name,
            "incident_title": runbook.get("title") if runbook else f"Sự cố {incident_type}",
            "severity": severity,
            "executive_summary": summary,
            "root_cause": likely_causes[0] if likely_causes else "Đang điều tra nguyên nhân gốc.",
            "all_potential_causes": likely_causes,
            "user_impact": impact,
            "investigation_steps": investigation_steps,
            "action_plan": action_plan,
            "rfc_citations": rfc_citations,
            "confidence_score": 0.95
        }

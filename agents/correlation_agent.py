"""
Incident Correlation Agent (Tác tử Tương quan Sự cố Đa Lỗi & Khử Nhiễu DAG)
Áp dụng đồ thị có hướng không chu trình (Directed Acyclic Graph - DAG) để mô hình hóa
quan hệ nhân quả hạ tầng mạng, phát hiện đa lỗi độc lập (Multi-Root-Cause) và triệt tiêu
các cảnh báo hệ quả lan truyền (Noise Reduction).
"""

from typing import Dict, Any, List
from analytics.correlation_engine import DAGCorrelationEngine

class IncidentCorrelationAgent:
    """Tác tử tương quan và khử nhiễu cảnh báo đa tín hiệu dựa trên mô hình DAG."""

    def __init__(self, name: str = "Incident Correlation Agent (DAG Engine)"):
        self.name = name
        self.engine = DAGCorrelationEngine()

    def correlate_anomalies(self, violations: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Thực hiện tương quan đa lỗi bằng mô hình DAG:
        - Nhóm các vi phạm vào các tầng hạ tầng (DNS -> TCP -> SSL -> HTTP -> App -> DOM -> UI)
        - Cô lập các Root Cause độc lập (kể cả khi xảy ra đồng thời)
        - Triệt tiêu các Cascading Faults do nút cha gây ra
        - Xuất sơ đồ Mermaid Diagram trực quan
        """
        raw_result = self.engine.correlate_violations(violations)
        
        raw_count = raw_result.get("raw_violations_count", 0)
        suppressed_count = raw_result.get("suppressed_alerts_count", 0)
        noise_reduction_pct = round((suppressed_count / raw_count) * 100, 1) if raw_count > 0 else 0.0

        dag_analysis = raw_result.get("dag_analysis", {})
        is_multi_fault = dag_analysis.get("is_multi_fault", False)
        root_causes = dag_analysis.get("root_causes", [])
        cascading_faults = dag_analysis.get("cascading_faults", [])
        mermaid_code = dag_analysis.get("mermaid_diagram", "")

        return {
            "agent_name": self.name,
            "has_incident": raw_result.get("has_incident", False),
            "overall_severity": raw_result.get("overall_severity", "HEALTHY"),
            "incident_type": raw_result.get("incident_type", "NO_INCIDENT"),
            "root_cause_summary": raw_result.get("root_cause_summary", "Không phát hiện sự cố."),
            "primary_issue": raw_result.get("primary_issue"),
            "raw_violations_count": raw_count,
            "suppressed_alerts_count": suppressed_count,
            "noise_reduction_pct": noise_reduction_pct,
            "correlated_signals": raw_result.get("correlated_signals", []),
            "deduplication_ratio": f"{suppressed_count}/{raw_count} cảnh báo hệ quả đã được triệt tiêu",
            "is_multi_fault": is_multi_fault,
            "root_causes": root_causes,
            "cascading_faults": cascading_faults,
            "dag_analysis": dag_analysis,
            "mermaid_diagram": mermaid_code
        }

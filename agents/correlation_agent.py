"""
Incident Correlation Agent (Tác tử Tương quan Sự cố & Khử Nhiễu)
Áp dụng cây phụ thuộc hạ tầng mạng (Layered Dependency Tree) để gom nhóm các cảnh báo rời rạc,
xác định sự cố gốc duy nhất và triệt tiêu các cảnh báo hệ quả (Noise Reduction).
"""

from typing import Dict, Any, List
from analytics.correlation_engine import RuleBasedCorrelationEngine

class IncidentCorrelationAgent:
    """Tác tử tương quan và khử nhiễu cảnh báo đa tín hiệu."""

    def __init__(self, name: str = "Incident Correlation Agent"):
        self.name = name
        self.engine = RuleBasedCorrelationEngine()

    def correlate_anomalies(self, violations: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Thực hiện tương quan các vi phạm từ Anomaly Detection Agent và trả về kết quả sự cố duy nhất.
        """
        raw_result = self.engine.correlate_violations(violations)
        
        raw_count = raw_result.get("raw_violations_count", 0)
        suppressed_count = raw_result.get("suppressed_alerts_count", 0)
        noise_reduction_pct = round((suppressed_count / raw_count) * 100, 1) if raw_count > 0 else 0.0

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
            "deduplication_ratio": f"{suppressed_count}/{raw_count} cảnh báo đã được triệt tiêu"
        }

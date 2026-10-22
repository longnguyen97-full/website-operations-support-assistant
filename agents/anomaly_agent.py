"""
Anomaly Detection Agent (Tác tử Phát hiện Bất thường)
Chịu trách nhiệm phân tích bằng chứng thô từ Probe Agent, phát hiện các vi phạm quy tắc kỹ thuật
và phát hiện đột biến thống kê Z-Score trên chuỗi thời gian lịch sử.
"""

from typing import Dict, Any, List, Optional
from analytics.rule_engine import RuleBasedAnomalyEngine
from analytics.statistical_detector import StatisticalAnomalyDetector

class AnomalyDetectionAgent:
    """Tác tử phát hiện bất thường kết hợp Luật chuyên môn & Thống kê."""

    def __init__(self, name: str = "Anomaly Detection Agent"):
        self.name = name
        self.rule_engine = RuleBasedAnomalyEngine()
        self.stat_detector = StatisticalAnomalyDetector()

    def analyze_evidence(
        self,
        evidence: Dict[str, Any],
        history_latencies: Optional[List[float]] = None
    ) -> Dict[str, Any]:
        """
        Phân tích tập bằng chứng kỹ thuật và trả về danh sách bất thường phát hiện được.
        """
        http_res = evidence.get("http", {})
        dns_res = evidence.get("dns", {})
        ssl_res = evidence.get("ssl", {})
        perf_res = evidence.get("performance")
        dom_res = evidence.get("dom")
        visual_res = evidence.get("visual")

        # 1. Đánh giá bộ luật chuẩn kỹ thuật
        rule_violations = self.rule_engine.evaluate_all_rules(
            http_res=http_res,
            dns_res=dns_res,
            ssl_res=ssl_res,
            perf_res=perf_res,
            dom_res=dom_res,
            visual_res=visual_res
        )

        # 2. Phân tích thống kê Z-Score trên chuỗi thời gian theo Công thức 3.1
        current_latency = (
            http_res.get("response_time_ms") or 
            (perf_res.get("total_time_ms") if perf_res else 0.0) or 0.0
        )
        z_analysis = self.stat_detector.analyze_latency(
            current_latency=current_latency,
            history_latencies=history_latencies or []
        )

        z_val = abs(float(z_analysis.get("z_score", 0.0)))
        w_latency = 1.5
        # Thành phần phạt trễ mạng thích ứng: w_latency * max(0, Z_t - 2.5) * 10 (Công thức 3.1)
        latency_penalty = round(w_latency * max(0.0, z_val - 2.5) * 10, 1)

        if z_analysis.get("is_anomaly") or latency_penalty > 0:
            rule_violations.append({
                "signal": "Z_SCORE_STATISTICAL",
                "rule_id": "STAT_Z_SCORE_SPIKE",
                "severity": z_analysis.get("severity", "WARNING"),
                "title": f"Bất thường Thống kê Z-Score (+{z_val:.2f})",
                "description": z_analysis.get("reason", "Độ trễ tăng đột biến so với phân phối lịch sử."),
                "weight": max(15, latency_penalty)
            })

        # 3. Tính toán Điểm bất thường tổng hợp S_composite theo Công thức 3.1:
        # S_composite = min(100, sum(w_i * I(Rule_i)) + w_latency * max(0, Z_t - 2.5) * 10)
        deterministic_rules_weight = sum(
            v.get("weight", 10) for v in rule_violations if v.get("signal") != "Z_SCORE_STATISTICAL"
        )
        composite_score = min(100.0, deterministic_rules_weight + latency_penalty)
        anomaly_score = round(composite_score, 1)

        # Phân loại 3 cấp độ vận hành theo chuẩn SRE SLA:
        # - S_composite < 25: HEALTHY
        # - 25 <= S_composite < 70: DEGRADED (WARNING)
        # - S_composite >= 70: CRITICAL
        if anomaly_score >= 70 or any(v.get("severity") == "CRITICAL" for v in rule_violations):
            overall_severity = "CRITICAL"
        elif anomaly_score >= 25 or any(v.get("severity") == "WARNING" for v in rule_violations):
            overall_severity = "WARNING"  # DEGRADED
        else:
            overall_severity = "HEALTHY"

        is_anomaly_detected = (anomaly_score >= 25) or (len(rule_violations) > 0)

        return {
            "agent_name": self.name,
            "is_anomaly_detected": is_anomaly_detected,
            "overall_severity": overall_severity,
            "anomaly_score": anomaly_score,
            "latency_penalty": latency_penalty,
            "violations_count": len(rule_violations),
            "violations": rule_violations,
            "z_score_analysis": z_analysis
        }

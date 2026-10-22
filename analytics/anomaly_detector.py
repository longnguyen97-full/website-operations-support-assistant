from typing import Dict, Any, List, Optional
from analytics.statistical_detector import StatisticalAnomalyDetector
from analytics.rule_engine import RuleBasedAnomalyEngine
from analytics.correlation_engine import DAGCorrelationEngine

class AnomalyDetectionOrchestrator:
    """
    Bộ điều phối phát hiện bất thường tổng hợp (Rule-based + Statistical):
    - Đánh giá bộ luật chuyên sâu theo tiêu chuẩn RFC 9110, RFC 1035, RFC 5280, RFC 8446 và W3C DOM.
    - Phân tích thống kê chuỗi thời gian Z-Score để bắt trọn đột biến độ trễ (Latency Spike).
    - Tương quan sự cố đa tín hiệu và cô lập lỗi bằng Đồ thị Causal DAG.
    """

    def __init__(self):
        self.stat_detector = StatisticalAnomalyDetector()
        self.rule_engine = RuleBasedAnomalyEngine()
        self.correlation_engine = DAGCorrelationEngine()

    def run_multi_signal_rule_statistical(
        self,
        http_res: Dict[str, Any],
        dns_res: Dict[str, Any],
        ssl_res: Dict[str, Any],
        perf_res: Optional[Dict[str, Any]] = None,
        dom_res: Optional[Dict[str, Any]] = None,
        visual_res: Optional[Dict[str, Any]] = None,
        history_latencies: Optional[List[float]] = None
    ) -> Dict[str, Any]:
        """
        Giám sát đa tín hiệu kết hợp Luật & Thống kê:
        1. Đánh giá 6 tầng tín hiệu kỹ thuật (HTTP, DNS, SSL, Perf, DOM, Visual).
        2. Phân tích thống kê chuỗi thời gian Z-Score trên độ trễ lịch sử.
        3. Tương quan đa lỗi đa tín hiệu bằng Causal DAG Engine.
        4. Tính toán điểm bất thường tổng hợp (Anomaly Score 0 - 100).
        """
        # 1. Chạy Rule-based Anomaly Engine
        rule_violations = self.rule_engine.evaluate_all_rules(
            http_res=http_res,
            dns_res=dns_res,
            ssl_res=ssl_res,
            perf_res=perf_res,
            dom_res=dom_res,
            visual_res=visual_res
        )

        # 2. Chạy Z-Score Anomaly Detector trên chuỗi thời gian lịch sử
        current_latency = http_res.get("response_time_ms") or (perf_res.get("total_time_ms") if perf_res else 0.0)
        z_analysis = self.stat_detector.analyze_latency(
            current_latency=current_latency,
            history_latencies=history_latencies or []
        )

        z_val = abs(float(z_analysis.get("z_score", 0.0)))
        w_latency = 1.5
        latency_penalty = round(w_latency * max(0.0, z_val - 2.5) * 10, 1)

        # Nếu Z-Score phát hiện bất thường (|Z| >= 2.5), thêm vào danh sách vi phạm
        if z_analysis.get("is_anomaly") or latency_penalty > 0:
            rule_violations.append({
                "signal": "Z_SCORE_STATISTICAL",
                "rule_id": "STAT_Z_SCORE_SPIKE",
                "severity": z_analysis.get("severity", "WARNING"),
                "title": f"Bất thường Thống kê Z-Score (+{z_val:.2f})",
                "description": z_analysis.get("reason", "Độ trễ tăng đột biến so với phương sai thống kê."),
                "weight": max(15, latency_penalty)
            })

        # 3. Chạy DAG-Based Incident Correlation (Tương quan sự cố & Khử nhiễu đa tầng)
        correlation_result = self.correlation_engine.correlate_violations(rule_violations)

        # 4. Tính toán Anomaly Score (0 - 100 điểm)
        deterministic_rules_weight = sum(
            v.get("weight", 10) for v in rule_violations if v.get("signal") != "Z_SCORE_STATISTICAL"
        )
        anomaly_score = round(min(100.0, deterministic_rules_weight + latency_penalty), 1)

        return {
            "mode": "MULTI_SIGNAL_RULE_STATISTICAL",
            "is_anomaly_detected": correlation_result["has_incident"],
            "overall_status": correlation_result["overall_severity"],
            "anomaly_score": anomaly_score,
            "incident_type": correlation_result["incident_type"],
            "root_cause_summary": correlation_result["root_cause_summary"],
            "primary_issue": correlation_result.get("primary_issue"),
            "raw_violations_count": correlation_result.get("raw_violations_count", 0),
            "suppressed_alerts_count": correlation_result.get("suppressed_alerts_count", 0),
            "correlated_signals": correlation_result.get("correlated_signals", []),
            "dag_analysis": correlation_result.get("dag_analysis", {}),
            "z_score_analysis": z_analysis,
            "all_violations": rule_violations
        }

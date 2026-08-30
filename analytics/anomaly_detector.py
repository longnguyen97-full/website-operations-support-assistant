from typing import Dict, Any, List, Optional
from analytics.statistical_detector import StatisticalAnomalyDetector
from analytics.rule_engine import RuleBasedAnomalyEngine
from analytics.correlation_engine import RuleBasedCorrelationEngine

class AnomalyDetectionOrchestrator:
    """
    Bộ điều phối phát hiện bất thường tổng hợp (Rule-based + Statistical).
    Hỗ trợ 2 chế độ vận hành đối chứng:
    1. THRESHOLD_BASED (Cảnh báo dựa trên ngưỡng truyền thống)
    2. MULTI_SIGNAL_RULE_STATISTICAL (Giám sát đa tín hiệu kết hợp Luật & Thống kê - Không sử dụng AI)
    """

    def __init__(self):
        self.stat_detector = StatisticalAnomalyDetector()
        self.rule_engine = RuleBasedAnomalyEngine()
        self.correlation_engine = RuleBasedCorrelationEngine()

    def run_threshold_based_monitoring(
        self,
        http_res: Dict[str, Any],
        latency_threshold_ms: float = 2000.0,
        expected_status: int = 200
    ) -> Dict[str, Any]:
        """
        CẤU HÌNH 1: Cảnh báo dựa trên ngưỡng truyền thống (Threshold-based Alerting).
        Đặc điểm:
        - Đơn tín hiệu (Single Signal): Chỉ kiểm tra mã HTTP status và ngưỡng thời gian phản hồi cố định.
        - Không áp dụng thống kê Z-Score / IQR.
        - Không có cơ chế tương quan tín hiệu (No Correlation).
        - Bắn cảnh báo độc lập, dễ sinh cảnh báo rác / trùng lặp (Noisy Alerts).
        """
        status_code = http_res.get("status_code")
        resp_time = http_res.get("response_time_ms") or 0.0
        error = http_res.get("error")

        violations = []
        is_incident = False

        if status_code is None or error:
            is_incident = True
            violations.append({
                "type": "HTTP_CONNECTION_FAILURE",
                "message": f"Không kết nối được: {error or 'Unknown Error'}"
            })
        elif status_code != expected_status:
            is_incident = True
            violations.append({
                "type": "STATUS_CODE_THRESHOLD_VIOLATION",
                "message": f"Mã HTTP {status_code} khác ngưỡng mong đợi {expected_status}"
            })

        if resp_time > latency_threshold_ms:
            is_incident = True
            violations.append({
                "type": "LATENCY_THRESHOLD_VIOLATION",
                "message": f"Thời gian phản hồi {resp_time}ms vượt ngưỡng {latency_threshold_ms}ms"
            })

        severity = "CRITICAL" if (status_code is None or (status_code and status_code >= 500)) else ("WARNING" if is_incident else "HEALTHY")

        return {
            "mode": "THRESHOLD_BASED",
            "is_anomaly_detected": is_incident,
            "overall_status": severity,
            "violations_count": len(violations),
            "violations": violations,
            "alert_noisy": True,  # Cảnh báo truyền thống không có khử nhiễu
            "summary": "Phát hiện vi phạm ngưỡng tĩnh đơn lẻ." if is_incident else "Tất cả chỉ số nằm trong ngưỡng cho phép."
        }

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
        CẤU HÌNH 2: Giám sát đa tín hiệu kết hợp Luật & Thống kê (Multi-Signal Rule & Statistical - Không AI).
        Đặc điểm:
        - Giám sát đồng thời 6 tín hiệu (HTTP, DNS, SSL, Hiệu năng SRE, DOM, Visual).
        - Phân tích thống kê chuỗi thời gian (Z-Score + IQR + Moving Average Jump).
        - Đánh giá bộ luật chuyên sâu theo tiêu chuẩn RFC 9110, RFC 1035, RFC 5280, RFC 8446.
        - Khử nhiễu và tương quan sự cố theo luật cứng (Rule-based Incident Correlation & Noise Reduction).
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

        # Nếu Z-Score phát hiện bất thường (|Z| >= 2.5), thêm vào danh sách vi phạm
        if z_analysis.get("is_anomaly"):
            rule_violations.append({
                "signal": "Z_SCORE_STATISTICAL",
                "rule_id": "STAT_Z_SCORE_SPIKE",
                "severity": z_analysis.get("severity", "WARNING"),
                "title": f"Bất thường Thống kê Z-Score (+{z_analysis.get('z_score')})",
                "description": z_analysis.get("reason", "Độ trễ tăng đột biến so với phương sai thống kê."),
                "weight": 25 if z_analysis.get("severity") == "CRITICAL" else 15
            })

        # 3. Chạy Rule-Based Incident Correlation (Tương quan sự cố & Triệt tiêu cảnh báo trùng)
        correlation_result = self.correlation_engine.correlate_violations(rule_violations)

        # 4. Tính toán Anomaly Score (0 - 100 điểm)
        total_weight = sum(v.get("weight", 10) for v in rule_violations)
        anomaly_score = min(100, total_weight)

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
            "z_score_analysis": z_analysis,
            "all_violations": rule_violations
        }

    def compare_three_configurations(
        self,
        website_info: Dict[str, Any],
        http_res: Dict[str, Any],
        dns_res: Dict[str, Any],
        ssl_res: Dict[str, Any],
        perf_res: Optional[Dict[str, Any]] = None,
        dom_res: Optional[Dict[str, Any]] = None,
        visual_res: Optional[Dict[str, Any]] = None,
        history_latencies: Optional[List[float]] = None,
        active_baseline: Optional[Dict[str, Any]] = None,
        latency_threshold_ms: float = 2000.0,
        expected_status: int = 200,
        agent_result: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Thực hiện đánh giá đối chứng toàn diện 3 Cấu hình Giám sát trên cùng một phiên quét:
        - Cấu hình 1 (Truyền thống): Cảnh báo dựa trên ngưỡng cứng (Threshold-Based).
        - Cấu hình 2 (Bán tự động): Giám sát đa tín hiệu kết hợp Luật RFC & Z-Score (Không AI).
        - Cấu hình 3 (Agentic AI Tự động): Hệ thống Đa tác tử tự hành (Multi-Agent Reasoning Studio).
        """
        # 1. Chạy Cấu hình 1
        cfg1_res = self.run_threshold_based_monitoring(
            http_res=http_res,
            latency_threshold_ms=latency_threshold_ms,
            expected_status=expected_status
        )

        # 2. Chạy Cấu hình 2
        cfg2_res = self.run_multi_signal_rule_statistical(
            http_res=http_res,
            dns_res=dns_res,
            ssl_res=ssl_res,
            perf_res=perf_res,
            dom_res=dom_res,
            visual_res=visual_res,
            history_latencies=history_latencies
        )

        # 3. Chạy hoặc lấy kết quả Cấu hình 3 (Agentic AI)
        if agent_result is None:
            from agents.orchestrator import MonitoringOrchestratorAgent
            orchestrator = MonitoringOrchestratorAgent()
            cfg3_res = orchestrator.run_agentic_workflow(
                website_info=website_info,
                active_baseline=active_baseline,
                history_latencies=history_latencies,
                enable_visual=False
            )
        else:
            cfg3_res = agent_result

        raw_alerts = cfg2_res.get("raw_violations_count", 0)
        suppressed_alerts = cfg2_res.get("suppressed_alerts_count", 0)
        noise_reduction_pct = round((suppressed_alerts / raw_alerts) * 100, 1) if raw_alerts > 0 else 0.0

        return {
            "config_1_threshold_based": cfg1_res,
            "config_2_multi_signal": cfg2_res,
            "config_3_agentic_ai": cfg3_res,
            "evaluation_metrics": {
                "noise_reduction_rate_pct": noise_reduction_pct,
                "raw_alerts_count": raw_alerts,
                "suppressed_alerts_count": suppressed_alerts,
                "cfg1_alerts_count": cfg1_res.get("violations_count", 0),
                "cfg2_incident_type": cfg2_res.get("incident_type"),
                "cfg3_severity": cfg3_res.get("overall_severity"),
                "cfg3_execution_steps": len(cfg3_res.get("execution_trace", [])),
                "has_root_cause_context": bool(cfg2_res.get("root_cause_summary")),
                "z_score_value": cfg2_res.get("z_score_analysis", {}).get("z_score", 0.0),
                "is_z_score_spike": cfg2_res.get("z_score_analysis", {}).get("is_anomaly", False)
            }
        }


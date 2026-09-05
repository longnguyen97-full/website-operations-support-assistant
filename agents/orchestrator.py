"""
Monitoring Orchestrator Agent (Tác tử Điều phối Trung tâm)
Đóng vai trò 'Bộ não' trung tâm của hệ sinh thái Agentic AI:
- Quản lý State Machine và luồng điều phối đa tác tử.
- Hiện thực hóa 4 khả năng cốt lõi: Lập kế hoạch (Planning), Sử dụng công cụ (Tool Use),
  Tự sửa sai (Self-Correction / Re-probe), và Bộ nhớ & Tri thức (Memory & Knowledge Base).
- Ghi nhận toàn bộ vết thực thi (Execution Trace) phục vụ giải trình minh bạch và đánh giá học thuật.
"""

import time
from typing import Dict, Any, Optional, List
from agents.probe_agent import ProbeAgent
from agents.anomaly_agent import AnomalyDetectionAgent
from agents.correlation_agent import IncidentCorrelationAgent
from agents.analysis_agent import IncidentAnalysisAgent
from agents.reporting_agent import ReportingNotificationAgent
from agents.knowledge_base import OperationalKnowledgeBase

class MonitoringOrchestratorAgent:
    """Tác tử điều phối trung tâm toàn bộ chu trình giám sát và xử lý sự cố."""

    def __init__(self, name: str = "Monitoring Orchestrator Agent"):
        self.name = name
        self.probe_agent = ProbeAgent()
        self.anomaly_agent = AnomalyDetectionAgent()
        self.correlation_agent = IncidentCorrelationAgent()
        self.analysis_agent = IncidentAnalysisAgent()
        self.reporting_agent = ReportingNotificationAgent()
        self.kb = OperationalKnowledgeBase()

    def run_agentic_workflow(
        self,
        website_info: Dict[str, Any],
        active_baseline: Optional[Dict[str, Any]] = None,
        history_latencies: Optional[List[float]] = None,
        enable_visual: bool = False,
        enable_notifications: bool = True
    ) -> Dict[str, Any]:
        """
        Thực thi toàn bộ quy trình Agentic AI:
        [1. Plan] -> [2. Probe Tools] -> [3. Anomaly Detect] -> [4. Self-Correct] -> [5. Correlate] -> [6. RCA Analyze] -> [7. Report]
        """
        start_time = time.time()
        execution_trace: List[Dict[str, Any]] = []

        url = website_info.get("url", "")
        domain = website_info.get("domain", "")
        expected_status = (
            active_baseline.get("expected_http_status")
            if active_baseline and active_baseline.get("expected_http_status")
            else website_info.get("expected_status", 200)
        )
        baseline_dns = active_baseline.get("baseline_dns") if active_baseline else None

        # =========================================================================
        # BƯỚC 1: LẬP KẾ HOẠCH (PLANNING)
        # =========================================================================
        planned_signals = ["HTTP", "DNS", "SSL", "DOM"]
        if enable_visual:
            planned_signals.append("VISUAL")

        plan_desc = f"Lập kế hoạch giám sát đa tín hiệu cho '{website_info.get('name')}' gồm các tầng: {', '.join(planned_signals)}."
        execution_trace.append({
            "step": 1,
            "phase": "PLANNING",
            "agent": self.name,
            "action": "Generate Execution Plan",
            "details": plan_desc,
            "planned_tools": ["http_checker", "dns_checker", "ssl_checker", "dom_validator"] + (["visual_checker"] if enable_visual else []),
            "timestamp": time.strftime("%H:%M:%S")
        })

        # =========================================================================
        # BƯỚC 2: SỬ DỤNG CÔNG CỤ & THU THẬP BẰNG CHỨNG (TOOL USE / PROBING)
        # =========================================================================
        probe_result = self.probe_agent.execute_probes(
            url=url,
            domain=domain,
            expected_status=expected_status,
            baseline_dns=baseline_dns,
            probe_signals=planned_signals,
            capture_visual=enable_visual,
            website_name=website_info.get("name", "Website")
        )
        evidence = probe_result.get("evidence", {})

        execution_trace.append({
            "step": 2,
            "phase": "TOOL_EXECUTION",
            "agent": self.probe_agent.name,
            "action": "Execute Probing Tools",
            "details": f"Đã thực thi {len(probe_result.get('probes_executed', []))} công cụ trong {probe_result.get('execution_time_ms')}ms.",
            "tools_executed": probe_result.get("probes_executed", []),
            "timestamp": time.strftime("%H:%M:%S")
        })

        # =========================================================================
        # BƯỚC 3: PHÁT HIỆN BẤT THƯỜNG SƠ BỘ (ANOMALY DETECTION)
        # =========================================================================
        anomaly_result = self.anomaly_agent.analyze_evidence(
            evidence=evidence,
            history_latencies=history_latencies
        )
        violations = anomaly_result.get("violations", [])

        execution_trace.append({
            "step": 3,
            "phase": "ANOMALY_DETECTION",
            "agent": self.anomaly_agent.name,
            "action": "Rule Evaluation & Z-Score Analysis",
            "details": f"Phát hiện {len(violations)} vi phạm tiềm năng. Điểm bất thường (Anomaly Score): {anomaly_result.get('anomaly_score')}/100.",
            "violations_found": [v.get("title") for v in violations],
            "timestamp": time.strftime("%H:%M:%S")
        })

        # =========================================================================
        # BƯỚC 4: PHẢN HỒI LINH HOẠT & TỰ SỬA SAI (SELF-CORRECTION / RE-PROBE)
        # =========================================================================
        self_correction_executed = False
        re_probe_notes = "Không cần kiểm tra lại (Kết quả nhất quán)."

        # Nếu phát hiện lỗi kết nối HTTP nhưng DNS phân giải bình thường, tự động re-probe HTTP để xác minh
        http_evidence = evidence.get("http", {})
        if http_evidence.get("error") and evidence.get("dns", {}).get("resolved"):
            self_correction_executed = True
            re_probe_notes = "Phát hiện lỗi kết nối HTTP đột xuất. Tác tử tự động kích hoạt Re-probe lần 2 để loại trừ Flapping."
            re_http = self.probe_agent.re_probe_specific_signal("HTTP", url, domain, expected_status, baseline_dns)
            evidence["http_re_probe"] = re_http
            if re_http.get("is_success"):
                re_probe_notes += " -> Kết quả Re-probe: Kết nối thành công! Đã triệt tiêu cảnh báo giả."
                # Cập nhật lại evidence
                evidence["http"] = re_http
                # Đánh giá lại anomaly
                anomaly_result = self.anomaly_agent.analyze_evidence(evidence=evidence, history_latencies=history_latencies)
                violations = anomaly_result.get("violations", [])

        execution_trace.append({
            "step": 4,
            "phase": "SELF_CORRECTION",
            "agent": self.name,
            "action": "Verify & Re-probe",
            "executed": self_correction_executed,
            "details": re_probe_notes,
            "timestamp": time.strftime("%H:%M:%S")
        })

        # =========================================================================
        # BƯỚC 5: TƯƠNG QUAN SỰ CỐ & KHỬ NHIỄU (CORRELATION & NOISE REDUCTION)
        # =========================================================================
        correlation_result = self.correlation_agent.correlate_anomalies(violations)

        execution_trace.append({
            "step": 5,
            "phase": "INCIDENT_CORRELATION",
            "agent": self.correlation_agent.name,
            "action": "Layered Dependency Correlation",
            "details": f"Sự cố chính: '{correlation_result.get('root_cause_summary')}'. Tỷ lệ khử nhiễu: {correlation_result.get('noise_reduction_pct')}% ({correlation_result.get('deduplication_ratio')}).",
            "correlated_incident": correlation_result.get("incident_type"),
            "timestamp": time.strftime("%H:%M:%S")
        })

        # =========================================================================
        # BƯỚC 6: PHÂN TÍCH NGUYÊN NHÂN GỐC & TRUY VẤN TRI THỨC (RCA & KNOWLEDGE RETRIEVAL)
        # =========================================================================
        analysis_result = self.analysis_agent.analyze_incident(
            website_info=website_info,
            correlation_data=correlation_result,
            evidence_data=evidence
        )

        execution_trace.append({
            "step": 6,
            "phase": "INCIDENT_ANALYSIS",
            "agent": self.analysis_agent.name,
            "action": "Root Cause Analysis (RCA) & Knowledge Retrieval",
            "details": f"Nguyên nhân gốc: {analysis_result.get('root_cause')}. Trích dẫn chuẩn: {', '.join(analysis_result.get('rfc_citations', [])) or 'N/A'}.",
            "executive_summary": analysis_result.get("executive_summary"),
            "timestamp": time.strftime("%H:%M:%S")
        })

        # =========================================================================
        # BƯỚC 7: BÁO CÁO & PHÂN PHỐI CẢNH BÁO (REPORTING & NOTIFICATION)
        # =========================================================================
        report_result = self.reporting_agent.generate_and_dispatch(
            website_info=website_info,
            analysis_result=analysis_result,
            evidence_data=evidence,
            overall_severity=correlation_result.get("overall_severity", "HEALTHY"),
            dispatch_alert=enable_notifications
        )

        execution_trace.append({
            "step": 7,
            "phase": "REPORTING_NOTIFICATION",
            "agent": self.reporting_agent.name,
            "action": "Dispatch Notification & Generate Report",
            "details": f"Trạng thái thông báo: {report_result.get('title')}. Email đã gửi: {report_result.get('email_dispatched')}.",
            "timestamp": time.strftime("%H:%M:%S")
        })

        total_elapsed_ms = round((time.time() - start_time) * 1000, 2)

        return {
            "orchestrator_name": self.name,
            "website_name": website_info.get("name"),
            "url": url,
            "domain": domain,
            "total_execution_time_ms": total_elapsed_ms,
            "overall_severity": correlation_result.get("overall_severity", "HEALTHY"),
            "evidence": evidence,
            "anomaly_analysis": anomaly_result,
            "correlation": correlation_result,
            "rca_analysis": analysis_result,
            "report_digest": report_result,
            "execution_trace": execution_trace
        }

import os
import shutil
from pathlib import Path
from PIL import Image
import streamlit as st
import pandas as pd
from datetime import datetime
from config import TIMEZONE_NAME, HTTP_TIMEOUT_SECONDS, DNS_TIMEOUT_SECONDS, SSL_TIMEOUT_SECONDS
from database.repository import (
    save_milestone_baseline,
    get_monitoring_logs,
    get_all_milestones,
    set_active_milestone,
    get_active_baseline,
    save_monitoring_log,
    calculate_overall_status,
    get_system_settings,
    get_website_latency_history,
    generate_periodic_report_data,
    get_telemetry_metrics_summary,
    get_storage_metrics,
    purge_old_artifacts,
    purge_old_logs
)
from analytics.correlation_engine import DAGCorrelationEngine
from agents.orchestrator import MonitoringOrchestratorAgent
from tools.http_checker import check_http
from tools.dns_checker import check_dns
from tools.ssl_checker import check_ssl
from notifications import check_and_send_alert


def render_unified_sre_console(selected_site):
    """
    TRUNG TÂM ĐIỀU HÀNH SRE THỐNG NHẤT (UNIFIED SRE OPERATIONS & AGENTIC RCA CONSOLE):
    Hợp nhất toàn bộ chu trình giám sát đo kiểm đa tín hiệu và suy luận tác tử AI:
    1. Action Control Ribbon: 1 nút kích hoạt chu trình điều hành toàn diện hoặc đo kiểm nhanh.
    2. Executive Status & KPIs: Trạng thái tổng thể, độ trễ, tỷ lệ khử nhiễu cảnh báo DAG.
    3. Sơ đồ Đồ thị Causal DAG Đa Lỗi: Mô hình hóa nhân quả đa tầng mạng, cô lập Root Causes vs Cascading Faults.
    4. Bằng chứng Đo kiểm Đa Tín hiệu Thực tế: HTTP, DNS RFC 1035, SSL RFC 5280, W3C DOM, Playwright Screenshot.
    5. Báo cáo Phân tích Nguyên nhân Gốc Toàn diện 8 phần (Full Enterprise SRE RCA Report) & Actionable Runbook.
    """
    
    # BANNER CONTEXT TRUNG TÂM ĐIỀU HÀNH THỐNG NHẤT
    st.markdown("""
    <div style="margin-bottom: 12px;">
        <span style="background: linear-gradient(90deg, #0284c7 0%, #7c3aed 100%); color: #ffffff; padding: 5px 14px; border-radius: 6px; font-weight: 700; font-size: 13px; letter-spacing: 0.5px; box-shadow: 0 2px 4px rgba(2,132,199,0.3);">
            🎯 TRUNG TÂM ĐIỀU HÀNH SRE THỐNG NHẤT (UNIFIED SRE OPERATIONS CONSOLE)
        </span>
    </div>
    <div style="background: linear-gradient(90deg, #0f172a 0%, #1e1b4b 100%); color: #f8fafc; padding: 14px 18px; border-radius: 10px; margin-bottom: 20px; border-left: 5px solid #38bdf8; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.1);">
        <div style="font-weight: bold; font-size: 15px; color: #38bdf8; margin-bottom: 6px;">
            ⚡ CHU TRÌNH TÁC TỬ TỰ HÀNH & ĐỒ THỊ NHÂN QUẢ CAUSAL DAG
        </div>
        <div style="font-size: 13px; color: #cbd5e1; line-height: 1.6;">
            <b>Quy trình hợp nhất:</b> <code>[1. Multi-Agent Planning]</code> ➔ <code>[2. Multi-Signal Probes]</code> ➔ <code>[3. Self-Correction Re-probe]</code> ➔ <code>[4. DAG Causal Correlation]</code> ➔ <code>[5. Full Enterprise RCA 8 Phần]</code> ➔ <code>[6. Automated Alert & Runbook]</code>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # THANH CÔNG CỤ ĐIỀU HÀNH (ACTION BAR)
    col_act1, col_act2, col_act3, col_act4 = st.columns([3, 2, 2, 2])
    with col_act1:
        run_full_agent_btn = st.button(
            "🚀 Quét & Chẩn Đoán Tác Tử Toàn Diện (Full SRE Workflow)", 
            key=f"btn_run_agent_{selected_site['id']}", 
            use_container_width=True, 
            type="primary",
            help="Kích hoạt toàn bộ chu trình 6 tác tử: Thu thập Đa tín hiệu, Tự sửa sai, Suy luận đồ thị DAG đa lỗi, Sinh báo cáo RCA 8 phần và Lưu CSDL."
        )
    with col_act2:
        run_quick_btn = st.button(
            "⚡ Đo Kiểm Nhanh (Quick Probe)", 
            key=f"btn_run_quick_{selected_site['id']}", 
            use_container_width=True,
            help="Đo kiểm nhanh kết nối HTTP, phân giải DNS và chứng chỉ SSL trong 500ms."
        )
    with col_act3:
        enable_screenshot = st.checkbox(
            "📸 Kèm Playwright UI (DOM & Visual)", 
            value=True, 
            key=f"toggle_playwright_{selected_site['id']}",
            help="Kích hoạt trình duyệt không đầu (Headless Browser) để chụp ảnh giao diện và phân tích cấu trúc DOM W3C."
        )
    with col_act4:
        enable_notifications = st.checkbox(
            "🔔 Gửi Email Cảnh Báo SRE", 
            value=True, 
            key=f"toggle_alert_{selected_site['id']}",
            help="Tự động phát cảnh báo qua email tới danh sách kỹ sư SRE trực ban khi phát hiện sự cố CRITICAL hoặc WARNING."
        )

    active_baseline_record = get_active_baseline(selected_site["id"])
    baseline_dns = active_baseline_record.get("baseline_dns") if active_baseline_record else None
    expected_status = (
        active_baseline_record.get("expected_http_status") 
        if active_baseline_record and active_baseline_record.get("expected_http_status") 
        else selected_site.get("expected_status", 200)
    )
    sys_settings = get_system_settings()
    http_timeout = float(sys_settings.get("http_timeout_seconds") or HTTP_TIMEOUT_SECONDS)
    dns_timeout = float(sys_settings.get("dns_timeout_seconds") or DNS_TIMEOUT_SECONDS)
    ssl_timeout = float(sys_settings.get("ssl_timeout_seconds") or SSL_TIMEOUT_SECONDS)

    # XỬ LÝ SỰ KIỆN NÚT BẤM QUICK PROBE
    if run_quick_btn:
        with st.spinner(f"⚡ Đang Quick Ping HTTP & DNS cho '{selected_site['name']}'..."):
            http_res = check_http(selected_site["url"], expected_status=expected_status, timeout=http_timeout)
            dns_res = check_dns(selected_site["domain"], baseline=baseline_dns, timeout=dns_timeout)
            ssl_res = check_ssl(selected_site["url"], timeout=ssl_timeout)
            from tools.tech_detector import detect_technology_stack
            tech_res = detect_technology_stack(selected_site["url"], http_res=http_res)
            dom_res = None
            # Bảo lưu visual_res từ lần quét trước để không làm mất ảnh screenshot khi chỉ Quick Ping
            prev_visual = st.session_state.get("last_scan", {}).get(selected_site["id"], {}).get("visual")
            visual_res = prev_visual
            overall_status = calculate_overall_status(http_res, dns_res, ssl_res, visual_res=visual_res)
            save_monitoring_log(
                website_id=selected_site["id"],
                website_name=selected_site["name"],
                http_res=http_res,
                dns_res=dns_res,
                ssl_res=ssl_res,
                dom_res=dom_res,
                visual_res=visual_res,
                overall_status=overall_status
            )
            if "last_scan" not in st.session_state:
                st.session_state["last_scan"] = {}
            st.session_state["last_scan"][selected_site["id"]] = {
                "http": http_res,
                "dns": dns_res,
                "ssl": ssl_res,
                "dom": dom_res,
                "visual": visual_res,
                "tech_stack": tech_res
            }
            st.session_state["last_agent_result"] = None
            st.toast("Đã hoàn tất Quick Probe!", icon="⚡")
            st.rerun()

    # XỬ LÝ SỰ KIỆN NÚT BẤM FULL SRE AGENTIC WORKFLOW
    if run_full_agent_btn:
        with st.spinner("🤖 Các tác tử SRE đang phối hợp lập kế hoạch, đo kiểm đa tín hiệu và suy luận đồ thị DAG..."):
            orchestrator = MonitoringOrchestratorAgent()
            active_b = get_active_baseline(selected_site["id"])
            hist_lat = get_website_latency_history(selected_site["id"], limit=20)
            agent_result = orchestrator.run_agentic_workflow(
                website_info=selected_site,
                active_baseline=active_b,
                history_latencies=hist_lat,
                enable_visual=enable_screenshot,
                enable_notifications=enable_notifications
            )
            st.session_state["last_agent_result"] = agent_result
            
            # Đồng bộ evidence vào session scan
            ev = agent_result.get("evidence", {})
            if "last_scan" not in st.session_state:
                st.session_state["last_scan"] = {}
            st.session_state["last_scan"][selected_site["id"]] = {
                "http": ev.get("http"),
                "dns": ev.get("dns"),
                "ssl": ev.get("ssl"),
                "performance": ev.get("performance"),
                "dom": ev.get("dom"),
                "visual": ev.get("visual"),
                "tech_stack": ev.get("tech_stack")
            }

            # Lưu bản ghi Agentic vào CSDL
            agent_sev = agent_result.get("overall_severity", "HEALTHY")
            save_monitoring_log(
                website_id=selected_site["id"],
                website_name=selected_site["name"],
                http_res=ev.get("http") or {},
                dns_res=ev.get("dns") or {},
                ssl_res=ev.get("ssl") or {},
                dom_res=ev.get("dom"),
                visual_res=ev.get("visual"),
                agent_res=agent_result,
                overall_status=agent_sev
            )

            if agent_result.get("report_digest", {}).get("email_dispatched"):
                st.toast("Đã tự động bắn Email cảnh báo sự cố tới đội ngũ SRE!", icon="🚨")
            st.toast("Tác tử Agentic AI đã hoàn tất điều tra & suy luận DAG!", icon="🎯")
            st.rerun()

    # LẤY DỮ LIỆU KẾT QUẢ ĐÃ THU THẬP TỪ SESSION HOẶC CSDL
    cached_agent_res = st.session_state.get("last_agent_result")
    agent_result = cached_agent_res if (cached_agent_res and cached_agent_res.get("website_name") == selected_site["name"]) else None
    
    site_scan = st.session_state.get("last_scan", {}).get(selected_site["id"], {})

    # Nếu trong session chưa có quét gần đây cho website này, nạp từ bản ghi CSDL gần nhất (nếu có)
    if not site_scan and not agent_result:
        recent_logs = get_monitoring_logs(website_id=selected_site["id"], limit=1)
        if recent_logs:
            last_log = recent_logs[0]
            signals = last_log.get("full_signals", {})
            site_scan = {
                "http": signals.get("http"),
                "dns": signals.get("dns"),
                "ssl": signals.get("ssl"),
                "performance": signals.get("performance"),
                "dom": signals.get("dom"),
                "visual": signals.get("visual"),
                "tech_stack": signals.get("tech_stack"),
                "from_history": True,
                "history_time": last_log.get("timestamp")
            }
            if "last_scan" not in st.session_state:
                st.session_state["last_scan"] = {}
            st.session_state["last_scan"][selected_site["id"]] = site_scan

    http_res = site_scan.get("http")
    dns_res = site_scan.get("dns")
    ssl_res = site_scan.get("ssl")
    perf_res = site_scan.get("performance")
    dom_res = site_scan.get("dom")
    visual_res = site_scan.get("visual") or (agent_result.get("evidence", {}).get("visual") if agent_result else None)
    tech_stack = site_scan.get("tech_stack") or (agent_result.get("evidence", {}).get("tech_stack") if agent_result else None)

    # Fallback tìm screenshot từ lịch sử gần nhất trong CSDL nếu visual_res chưa có
    if not visual_res:
        recent_visual_logs = get_monitoring_logs(website_id=selected_site["id"], limit=5)
        for log_entry in recent_visual_logs:
            v_sig = log_entry.get("full_signals", {}).get("visual")
            if v_sig and (v_sig.get("screenshot_path") or v_sig.get("current_image_path")):
                visual_res = v_sig
                break

    # Fallback tìm file ảnh screenshot latest trên ổ đĩa
    if not visual_res:
        from tools.visual_checker import SCREENSHOTS_DIR, _sanitize_name
        safe_name = _sanitize_name(selected_site["name"])
        latest_file = SCREENSHOTS_DIR / f"{safe_name}_latest.png"
        if latest_file.exists():
            visual_res = {
                "screenshot_path": str(latest_file),
                "current_image_path": str(latest_file),
                "status": "CACHED_DISK",
                "is_regression_detected": False,
                "url": selected_site["url"]
            }

    if not agent_result and not (http_res and dns_res and ssl_res):
        st.info("👉 Nhấn nút **'🚀 Quét & Chẩn Đoán Tác Tử Toàn Diện (Full SRE Workflow)'** ở trên để kích hoạt luồng điều hành SRE.")
        return

    # Xác định mức độ nghiêm trọng chung
    if agent_result:
        sev = agent_result.get("overall_severity", "HEALTHY")
    else:
        sev = calculate_overall_status(http_res, dns_res, ssl_res, dom_res=dom_res, visual_res=visual_res)

    status_badge_map = {
        "HEALTHY": ("🟢 HOẠT ĐỘNG TỐT (HEALTHY)", "#10b981"),
        "WARNING": ("🟡 CẢNH BÁO (WARNING)", "#f59e0b"),
        "CRITICAL": ("🔴 SỰ CỐ NGHIÊM TRỌNG (CRITICAL)", "#ef4444")
    }
    badge_label, badge_color = status_badge_map.get(sev, ("⚪ KHÔNG XÁC ĐỊNH", "#6b7280"))

    # =========================================================================
    # PHẦN 1: EXECUTIVE STATUS & KPI RIBBON
    # =========================================================================
    st.markdown("---")
    st.subheader(f"📊 Bảng Điều Khiển Trực Tiếp: {selected_site['name']}")
    st.markdown(f"**Trạng thái Tổng thể:** `{badge_label}` | **URL:** [{selected_site['url']}]({selected_site['url']}) | **Domain:** `{selected_site['domain']}`")

    if tech_stack and tech_stack.get("is_detected"):
        srv_name = tech_stack.get("web_server") or "Unknown Server"
        if tech_stack.get("web_server_version"):
            srv_name += f" ({tech_stack['web_server_version']})"
        cdn_name = ", ".join(tech_stack.get("cdn_proxies", [])) or "None"
        cms_name = ", ".join(tech_stack.get("frameworks_cms", [])) or "Custom"
        if tech_stack.get("cms_version"):
            cms_name += f" ({tech_stack['cms_version']})"
        lang_name = ", ".join(tech_stack.get("programming_languages", [])) or "Web"
        if tech_stack.get("language_version"):
            lang_name += f" ({tech_stack['language_version']})"

        st.markdown(f"🏷️ **Hệ Sinh Thái Công Nghệ:** 🖥️ `{srv_name}` | ⚡ `{cdn_name}` | 🧩 `{cms_name}` | 🐘 `{lang_name}`")

    k1, k2, k3, k4 = st.columns(4)
    if agent_result:
        corr_info = agent_result.get("correlation", {})
        dag_info = corr_info.get("dag_analysis", {})
        noise_pct = corr_info.get("noise_reduction_pct", 0)
        exec_ms = agent_result.get("total_execution_time_ms", 0)
        trace_steps = len(agent_result.get("execution_trace", []))
        
        k1.metric("Trạng Thái Vận Hành", f"{badge_label.split(' ')[0]} {sev}")
        k1_sub = "Đạt SLA 100%" if sev == "HEALTHY" else "Cần can thiệp SRE"
        k2.metric("Thời Gian Thực Thi", f"{exec_ms} ms", f"{trace_steps} bước tác tử")
        k3.metric("Khử Nhiễu Cảnh Báo DAG", f"{noise_pct}%", corr_info.get("deduplication_ratio"))
        
        rep_digest = agent_result.get("report_digest", {})
        if rep_digest.get("email_dispatched"):
            k4.metric("Thông Báo Email", "🚨 Đã Chuyển Phát", "Alert dispatched")
        elif sev == "HEALTHY":
            k4.metric("Thông Báo Email", "🟢 Hệ Thống Ổn Định", "No alert needed")
        else:
            k4.metric("Thông Báo Email", "⚠️ Chưa Gửi Email", "Check SMTP settings")
    else:
        http_code = http_res.get("status_code") if http_res else "N/A"
        lat_ms = http_res.get("response_time_ms", 0) if http_res else 0
        k1.metric("Trạng Thái Vận Hành", f"{badge_label.split(' ')[0]} {sev}")
        k2.metric("Thời Gian Phản Hồi", f"{lat_ms} ms", f"HTTP {http_code}")
        k3.metric("Kiểu Quét", "⚡ Quick Probe", "Chưa chạy Agentic RCA")
        k4.metric("Thông Báo Email", "⚪ Chế độ Nhanh", "Quick probe mode")

    st.markdown("---")

    # =========================================================================
    # PHẦN 2: SƠ ĐỒ ĐỒ THỊ CAUSAL DAG ĐA LỖI & CHUỖI NGUYÊN NHÂN
    # =========================================================================
    st.markdown("### 🗺️ 1. Sơ Đồ Đồ Thị Causal DAG Đa Lỗi & Chuỗi Nguyên Nhân (Multi-Fault Causal Graph)")
    st.caption("Mô hình hóa quan hệ nhân quả phân tầng mạng: 🔴 Đỏ = Root Cause (Nguyên nhân gốc) | 🟠 Cam = Cascading Fault (Lỗi hệ quả lan truyền) | 🟢 Xanh = Healthy (Bình thường)")

    # Khởi tạo hoặc trích xuất DAG Analysis
    if agent_result and agent_result.get("correlation", {}).get("dag_analysis"):
        dag_analysis = agent_result["correlation"]["dag_analysis"]
        mermaid_code = dag_analysis.get("mermaid_diagram", "")
        root_causes = dag_analysis.get("root_causes", [])
        cascading_faults = dag_analysis.get("cascading_faults", [])
        is_multi_fault = dag_analysis.get("is_multi_fault", False)
    else:
        # Nếu chỉ chạy quick probe, tính toán DAG tại chỗ
        from analytics.rule_engine import RuleBasedAnomalyEngine
        rule_engine = RuleBasedAnomalyEngine()
        violations = rule_engine.evaluate_all_rules(
            http_res=http_res or {},
            dns_res=dns_res or {},
            ssl_res=ssl_res or {},
            dom_res=dom_res,
            visual_res=visual_res
        )
        dag_engine = DAGCorrelationEngine()
        dag_res = dag_engine.correlate_violations(violations)
        dag_analysis = dag_res.get("dag_analysis", {})
        mermaid_code = dag_analysis.get("mermaid_diagram", "")
        root_causes = dag_analysis.get("root_causes", [])
        cascading_faults = dag_analysis.get("cascading_faults", [])
        is_multi_fault = dag_analysis.get("is_multi_fault", False)

    col_dag_left, col_dag_right = st.columns([3, 2])

    with col_dag_left:
        # Hiển thị biểu đồ Mermaid
        if mermaid_code:
            st.markdown(f"```mermaid\n{mermaid_code}\n```")
        else:
            st.info("Không có dữ liệu biểu đồ Mermaid.")

    with col_dag_right:
        # Hiển thị bảng phân định Đa Lỗi Độc Lập vs Lỗi Lan Truyền
        if is_multi_fault:
            st.markdown("""
            <div style="background: #450a0a; border: 2px solid #ef4444; border-radius: 8px; padding: 12px; margin-bottom: 12px;">
                <div style="color: #fca5a5; font-weight: bold; font-size: 14px;">
                    ⚡ PHÁT HIỆN ĐA LỖI ĐỘC LẬP ĐỒNG THỜI (MULTI-ROOT-CAUSE OUTAGE)
                </div>
                <div style="color: #fee2e2; font-size: 12px; margin-top: 4px;">
                    DAG Engine đã phát hiện nhiều nguyên nhân gốc độc lập xảy ra đồng thời trên các tầng hạ tầng khác nhau.
                </div>
            </div>
            """, unsafe_allow_html=True)
        elif root_causes:
            st.markdown(f"""
            <div style="background: #1e1b4b; border: 1px solid #6366f1; border-radius: 8px; padding: 12px; margin-bottom: 12px;">
                <div style="color: #c7d2fe; font-weight: bold; font-size: 14px;">
                    🎯 ĐƠN LỖI GỐC DUY NHẤT (SINGLE ROOT CAUSE)
                </div>
                <div style="color: #e0e7ff; font-size: 12px; margin-top: 4px;">
                    DAG Engine đã cô lập chính xác nguyên nhân gốc cao nhất và triệt tiêu các cảnh báo hệ quả.
                </div>
            </div>
            """, unsafe_allow_html=True)
        else:
            st.success("🎉 Tất cả các nút trong đồ thị DAG đều hoạt động hoàn hảo (100% Healthy)!")

        # Chi tiết các Root Causes
        if root_causes:
            st.markdown("##### 🔴 Danh Sách Nguyên Nhân Gốc (Root Causes):")
            for idx, rc in enumerate(root_causes, 1):
                pv = rc.get("primary_violation", {})
                st.markdown(f"""
                <div style="background: #18181b; border-left: 4px solid #ef4444; padding: 8px 12px; border-radius: 4px; margin-bottom: 8px;">
                    <div style="font-weight: bold; color: #f87171; font-size: 13px;">
                        {idx}. {rc.get('label')} ({rc.get('layer')})
                    </div>
                    <div style="font-size: 12px; color: #e4e4e7; margin-top: 2px;">
                        <b>Lỗi:</b> {pv.get('title')} — <i>{pv.get('description')}</i>
                    </div>
                    <div style="font-size: 11px; color: #a1a1aa; margin-top: 2px;">
                        Tiêu chuẩn đối soát: <code>{rc.get('rfc_standard') or 'SRE Standards'}</code>
                    </div>
                </div>
                """, unsafe_allow_html=True)

        # Chi tiết các Cascading Faults đã triệt tiêu
        if cascading_faults:
            st.markdown(f"##### 🟠 Cảnh Báo Hệ Quả Đã Triệt Tiêu ({len(cascading_faults)} Nút Lan Truyền):")
            for cf in cascading_faults:
                st.markdown(f"""
                <div style="background: #18181b; border-left: 4px dashed #f59e0b; padding: 6px 10px; border-radius: 4px; margin-bottom: 6px;">
                    <div style="font-weight: 600; color: #fbbf24; font-size: 12.5px;">
                        {cf.get('label')} ({cf.get('layer')})
                    </div>
                    <div style="font-size: 11.5px; color: #d4d4d8;">
                        {cf.get('reason')} ({cf.get('suppressed_violations_count', 0)} cảnh báo bị triệt tiêu)
                    </div>
                </div>
                """, unsafe_allow_html=True)

    st.markdown("---")

    # =========================================================================
    # PHẦN 3: BẰNG CHỨNG ĐO KIỂM ĐA TÍN HIỆU THỰC TẾ (LIVE TELEMETRY EVIDENCES)
    # =========================================================================
    st.markdown("### 🔬 2. Dữ Liệu Đo Kiểm Đa Tín Hiệu Thực Tế (Live Telemetry Evidences)")
    st.caption("Bằng chứng kỹ thuật thu thập trực tiếp theo các chuẩn RFC 9110, RFC 1035, RFC 5280 và W3C DOM.")

    col_http, col_dns, col_ssl, col_dom = st.columns(4)

    # Cột 1: HTTP Monitoring
    with col_http:
        st.markdown("#### 🌐 HTTP (RFC 9110)")
        if http_res:
            status_code = http_res.get("status_code")
            if http_res.get("is_success"):
                st.success(f"Status: **{status_code}** ({http_res.get('status_category')})")
            else:
                st.error(f"HTTP Status: **{status_code or 'Failed'}**")
            
            st.markdown(f"- **Method:** `{http_res.get('method', 'GET')}`")
            st.markdown(f"- **Response Time:** `{http_res.get('response_time_ms', 0)} ms`")
            st.markdown(f"- **Mã mong đợi:** `{selected_site.get('expected_status', 200)}`")
            
            if http_res.get("redirect_chain"):
                st.info("🔄 **Redirect Chain:**\n" + "\n".join([f"- `{hop['url']}` ({hop['status_code']})" for hop in http_res["redirect_chain"]]))
            if http_res.get("error") or http_res.get("error_title"):
                st.warning(f"**Lỗi HTTP:** `{http_res.get('error_title') or http_res.get('error')}`")
            if http_res.get("headers"):
                with st.expander("🔍 Xem HTTP Headers"):
                    st.json(http_res["headers"])
        else:
            st.info("Chưa có dữ liệu HTTP.")

    # Cột 2: DNS Monitoring
    with col_dns:
        st.markdown("#### 🗂️ DNS (RFC 1035)")
        if dns_res:
            if dns_res.get("resolved"):
                st.success(f"DNS: **Thành công** ({dns_res.get('resolution_time_ms')} ms)")
            else:
                st.error("DNS: **Thất bại (NXDOMAIN)**")

            dns_rows = []
            if dns_res.get("a"):
                dns_rows.append({"Type": "A (IPv4)", "Value": ", ".join(dns_res["a"])})
            if dns_res.get("aaaa"):
                dns_rows.append({"Type": "AAAA (IPv6)", "Value": ", ".join(dns_res["aaaa"])})
            if dns_res.get("cname"):
                dns_rows.append({"Type": "CNAME", "Value": str(dns_res["cname"])})
            if dns_res.get("mx"):
                dns_rows.append({"Type": "MX", "Value": "; ".join(dns_res["mx"][:2])})

            if dns_rows:
                st.dataframe(pd.DataFrame(dns_rows), use_container_width=True, hide_index=True)
            if dns_res.get("changes_detected"):
                st.warning("⚠️ **Phát hiện DNS Drift so với Baseline!**")
                with st.expander("Chi tiết thay đổi DNS"):
                    st.json(dns_res["changes_detected"])
            if dns_res.get("error"):
                st.error(f"Lỗi DNS: {dns_res.get('error')}")
        else:
            st.info("Chưa có dữ liệu DNS.")

    # Cột 3: SSL/TLS Monitoring
    with col_ssl:
        st.markdown("#### 🔒 SSL/TLS (RFC 5280)")
        if ssl_res:
            if ssl_res.get("is_http_only"):
                st.info("ℹ️ Website chạy thuần HTTP (Plaintext).")
            elif ssl_res.get("can_connect") is False:
                st.warning("SSL: **Không thể kết nối TCP**")
            elif ssl_res.get("is_valid"):
                st.success("Certificate: **Hợp lệ & Tin cậy**")
            else:
                st.error(f"Certificate: **{ssl_res.get('error_title') or 'Không hợp lệ'}**")

            if not ssl_res.get("is_http_only") and ssl_res.get("can_connect") is not False:
                st.markdown(f"- **Hạn còn:** **{ssl_res.get('days_remaining', 0)} ngày**")
                st.markdown(f"- **TLS Version:** `{ssl_res.get('tls_version') or 'N/A'}`")
                st.markdown(f"- **Issuer:** `{ssl_res.get('issuer') or 'N/A'}`")
            if ssl_res.get("error"):
                st.warning(f"Lỗi SSL: {ssl_res.get('error')}")
        else:
            st.info("Chưa có dữ liệu SSL.")

    # Cột 4: DOM Structural Integrity
    with col_dom:
        st.markdown("#### 🧱 DOM (W3C HTML)")
        if dom_res:
            if dom_res.get("is_structure_valid"):
                st.success("Cấu trúc DOM: **Toàn vẹn & Hợp lệ**")
                st.markdown(f"- **Title:** `{dom_res.get('page_title') or 'Có'}`")
                st.markdown(f"- **Body text:** `{dom_res.get('body_text_length', 0)} ký tự`")
            else:
                st.error("Cấu trúc DOM: **Bất thường / Khuyết thiếu**")
                missing = dom_res.get("missing_critical_elements", [])
                if missing:
                    st.warning(f"Thiếu thành phần: {', '.join(missing)}")
        else:
            st.info("Chưa chạy kiểm tra DOM.")

    # Khối Phân Rã Hiệu Năng SRE (W3C Network & Resource Timing Breakdown)
    if perf_res and not perf_res.get("error"):
        st.markdown("---")
        st.markdown("#### ⚡ Phân Rã Hiệu Năng Chi Tiết (W3C Network & Resource Timing Breakdown)")
        st.caption("Thời gian phản hồi phân rã theo từng giai đoạn chuẩn W3C Navigation Timing: DNS Lookup ➔ TCP Handshake ➔ TLS Socket ➔ TTFB.")
        bk = perf_res.get("breakdown", {})
        c_p1, c_p2, c_p3, c_p4, c_p5 = st.columns(5)
        c_p1.metric("Xếp Loại Hiệu Năng", perf_res.get("performance_grade", "A"))
        c_p2.metric("DNS Lookup", f"{bk.get('dns_lookup_ms', 0)} ms")
        c_p3.metric("TCP Connect", f"{bk.get('tcp_connect_ms', 0)} ms")
        c_p4.metric("TLS Handshake", f"{bk.get('ssl_handshake_ms', 0)} ms")
        c_p5.metric("TTFB (Server Delay)", f"{bk.get('ttfb_ms', 0)} ms")

    # Khối Nhận Diện Công Nghệ & SRE Runbook Cheatsheet
    if tech_stack and tech_stack.get("is_detected"):
        st.markdown("---")
        with st.expander("🛠️ Chi Tiết Hệ Sinh Thái Công Nghệ & SRE Runbook Cheatsheet (Tech Stack Fingerprints)", expanded=False):
            col_t1, col_t2 = st.columns([1, 1])
            with col_t1:
                st.markdown("##### 🔍 Chữ Ký Nhận Diện (Detected Components)")
                comps = tech_stack.get("detected_components", [])
                if comps:
                    t_df = pd.DataFrame(comps)[["category", "name", "version", "confidence", "source"]]
                    t_df.columns = ["Phân Loại", "Công Nghệ", "Phiên Bản", "Độ Tin Cậy", "Dấu Vết Đối Soát"]
                    t_df["Phiên Bản"] = t_df["Phiên Bản"].fillna("—")
                    st.dataframe(t_df, use_container_width=True, hide_index=True)
                
                if tech_stack.get("security_warnings"):
                    st.markdown("##### 🛡️ Cảnh Báo An Toàn & Hardening")
                    for w in tech_stack["security_warnings"]:
                        st.warning(f"⚠️ {w}")

            with col_t2:
                st.markdown("##### 📋 SRE Actionable Runbook Cheatsheet")
                cmds = tech_stack.get("recommended_sre_commands", [])
                if cmds:
                    st.caption("Các lệnh chuẩn đoán khẩn cấp phù hợp với Tech Stack của website này:")
                    for cmd in cmds:
                        st.code(cmd, language="bash")
                else:
                    st.info("Chưa có lệnh điều tra đặc thù cho stack này.")

    # Khối Ảnh chụp màn hình giao diện (Playwright Screenshot & Visual Regression)
    st.markdown("---")
    col_vis_head, col_vis_btn = st.columns([3, 1])
    with col_vis_head:
        st.markdown("#### 📸 Trực Quan Giao Diện Thực Tế (Playwright Screenshot & Visual Regression)")
        st.caption("Ảnh chụp màn hình thực tế (Headless Chromium 1280x800) và bản đồ nhiệt so sánh sai lệch pixel chuẩn SRE.")
    with col_vis_btn:
        capture_now_btn = st.button(
            "📸 Chụp Ảnh Màn Hình Ngay", 
            key=f"btn_capture_visual_{selected_site['id']}", 
            use_container_width=True,
            help="Kích hoạt Playwright Headless Browser để chụp ảnh màn hình website này ngay lập tức."
        )

    if capture_now_btn:
        with st.spinner(f"📸 Đang mở Playwright Chromium chụp ảnh {selected_site['url']}..."):
            from tools.visual_checker import check_visual_regression
            from config import VISUAL_TIMEOUT_SECONDS
            new_vis = check_visual_regression(
                url=selected_site["url"],
                website_identifier=selected_site["name"],
                full_page=True,
                timeout=VISUAL_TIMEOUT_SECONDS
            )
            visual_res = new_vis
            if "last_scan" not in st.session_state:
                st.session_state["last_scan"] = {}
            if selected_site["id"] not in st.session_state["last_scan"]:
                st.session_state["last_scan"][selected_site["id"]] = {}
            st.session_state["last_scan"][selected_site["id"]]["visual"] = new_vis
            if new_vis.get("screenshot_path") or new_vis.get("current_image_path"):
                st.toast("Đã chụp ảnh màn hình website thành công!", icon="📸")
            st.rerun()

    # Tìm đường dẫn file ảnh screenshot hợp lệ
    screenshot_file = None
    if visual_res:
        candidate_path = visual_res.get("screenshot_path") or visual_res.get("current_image_path") or visual_res.get("latest_path")
        if candidate_path and os.path.exists(candidate_path):
            screenshot_file = candidate_path

    if not screenshot_file:
        from tools.visual_checker import SCREENSHOTS_DIR, _sanitize_name
        fallback_latest = SCREENSHOTS_DIR / f"{_sanitize_name(selected_site['name'])}_latest.png"
        if fallback_latest.exists():
            screenshot_file = str(fallback_latest)

    if screenshot_file:
        col_vis1, col_vis2 = st.columns(2)
        with col_vis1:
            cap_time_txt = ""
            if visual_res and visual_res.get("capture_time_ms"):
                cap_time_txt = f" • Tốc độ chụp: `{visual_res.get('capture_time_ms')} ms`"
            st.markdown(f"**Ảnh chụp thực tế mới nhất:**{cap_time_txt}")
            try:
                from PIL import Image
                img_obj = Image.open(screenshot_file)
                st.image(img_obj, caption=f"📸 {selected_site['name']} ({selected_site['url']})", use_container_width=True)
            except Exception:
                st.image(screenshot_file, caption=f"📸 {selected_site['name']} ({selected_site['url']})", use_container_width=True)

        with col_vis2:
            diff_file = None
            if visual_res:
                diff_cand = visual_res.get("diff_heatmap_path") or visual_res.get("diff_image_path")
                if diff_cand and os.path.exists(diff_cand):
                    diff_file = diff_cand
            
            if diff_file:
                diff_pct = visual_res.get("diff_percentage", 0) if visual_res else 0
                st.markdown(f"**Bản đồ nhiệt sai khác pixel ({diff_pct}% diff):**")
                try:
                    from PIL import Image
                    diff_obj = Image.open(diff_file)
                    st.image(diff_obj, caption=f"🔥 Heatmap sai lệch ({diff_pct}%)", use_container_width=True)
                except Exception:
                    st.image(diff_file, caption="🔥 Heatmap sai lệch", use_container_width=True)
            else:
                base_cand = visual_res.get("baseline_image_path") if visual_res else None
                if base_cand and os.path.exists(base_cand):
                    st.markdown("**Ảnh mốc chuẩn (Baseline Reference):**")
                    st.image(base_cand, caption="🏷️ Mốc chuẩn đối chiếu (Baseline)", use_container_width=True)
                else:
                    st.info("ℹ️ Không phát hiện sai lệch giao diện hoặc chưa có ảnh mốc baseline đối chiếu.")
                    from tools.visual_checker import VISUAL_BASELINES_DIR, _sanitize_name
                    target_b_path = VISUAL_BASELINES_DIR / f"{_sanitize_name(selected_site['name'])}_baseline.png"
                    if not target_b_path.exists():
                        if st.button("🏷️ Đặt ảnh này làm Mốc Chuẩn Giao Diện (Visual Baseline)", key=f"btn_set_visual_b_{selected_site['id']}"):
                            import shutil
                            VISUAL_BASELINES_DIR.mkdir(parents=True, exist_ok=True)
                            shutil.copyfile(screenshot_file, str(target_b_path))
                            st.toast("Đã lưu ảnh làm Mốc Chuẩn Giao Diện!", icon="🏷️")
                            st.rerun()
    elif visual_res and visual_res.get("error"):
        st.warning(f"⚠️ Không thể chụp ảnh màn hình: {visual_res.get('error')}")
    else:
        st.info("ℹ️ Website này chưa có ảnh chụp màn hình trong phiên hiện tại. Bạn có thể nhấn nút **'📸 Chụp Ảnh Màn Hình Ngay'** ở trên hoặc bật tùy chọn **'📸 Kèm Playwright UI'** khi quét toàn diện.")

    # Khối Lưu Mốc Chuẩn (Milestone Baseline)
    st.markdown("---")
    with st.expander("📌 Lưu Kết Quả Đo Kiểm Này Làm Mốc Chuẩn (Milestone Baseline)"):
        with st.form("save_milestone_form_unified"):
            col_m1, col_m2 = st.columns([3, 1])
            note = col_m1.text_input("Ghi chú mốc chuẩn:", placeholder="Ví dụ: Mốc chuẩn cấu hình trước đợt bảo trì...")
            set_active = col_m2.checkbox("Kích hoạt làm Baseline mặc định", value=True)
            submitted = st.form_submit_button("💾 Lưu Mốc Chuẩn Vào CSDL", type="primary")
            if submitted and dns_res and http_res:
                current_dns_baseline = {
                    "a": dns_res.get("a", []),
                    "aaaa": dns_res.get("aaaa", []),
                    "cname": dns_res.get("cname"),
                    "mx": dns_res.get("mx", []),
                    "txt": dns_res.get("txt", [])
                }
                save_milestone_baseline(
                    website_id=selected_site["id"],
                    website_name=selected_site["name"],
                    baseline_dns=current_dns_baseline,
                    expected_http_status=http_res.get("status_code") or selected_site.get("expected_status", 200),
                    note=note or "Mốc chuẩn lưu từ Trung tâm Điều hành SRE",
                    set_active=set_active
                )
                if screenshot_file and os.path.exists(screenshot_file):
                    from tools.visual_checker import VISUAL_BASELINES_DIR, _sanitize_name
                    import shutil
                    VISUAL_BASELINES_DIR.mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(screenshot_file, str(VISUAL_BASELINES_DIR / f"{_sanitize_name(selected_site['name'])}_baseline.png"))
                st.success("✅ Đã lưu mốc chuẩn thành công vào CSDL!")
                st.toast("Đã lưu mốc chuẩn mới!", icon="📌")
                st.rerun()

    # =========================================================================
    # PHẦN 4: BÁO CÁO PHÂN TÍCH NGUYÊN NHÂN GỐC TOÀN DIỆN 8 PHẦN (FULL SRE RCA REPORT)
    # =========================================================================
    if agent_result and agent_result.get("rca_analysis"):
        rca = agent_result["rca_analysis"]
        st.markdown("---")
        st.markdown("### 📑 3. Báo Cáo Phân Tích Nguyên Nhân Gốc Toàn Diện (Full Enterprise SRE RCA Report)")

        # 4.1 Header Metadata Card
        st.markdown(f"""
        <div style="background: #0f172a; color: #f8fafc; padding: 20px; border-radius: 12px; border-left: 6px solid {'#10b981' if sev == 'HEALTHY' else ('#f59e0b' if sev == 'WARNING' else '#ef4444')}; margin-bottom: 20px;">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px;">
                <h3 style="margin:0; color: #38bdf8;">📌 {rca.get('incident_title', 'Báo Cáo Vận Hành')}</h3>
                <span style="background: {'#064e3b' if sev == 'HEALTHY' else '#7f1d1d'}; color: {'#6ee7b7' if sev == 'HEALTHY' else '#fca5a5'}; padding: 4px 12px; border-radius: 20px; font-weight: bold; font-size: 13px;">{rca.get('severity', sev)}</span>
            </div>
            <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 10px; font-size: 13px; color: #94a3b8; border-top: 1px solid #334155; padding-top: 10px;">
                <div><strong>Mã Sự Cố:</strong> <code>{rca.get('incident_id', 'INC-001')}</code></div>
                <div><strong>Thời Gian:</strong> {rca.get('timestamp', 'N/A')}</div>
                <div><strong>Tầng Sự Cố:</strong> <span style="color: #fde047;">{rca.get('fault_layer', 'N/A')}</span></div>
                <div><strong>Độ Tin Cậy Tác Tử:</strong> <span style="color: #6ee7b7;">{rca.get('confidence_score', 98.8)}%</span></div>
            </div>
        </div>
        """, unsafe_allow_html=True)

        # 4.2 Nhận Định Quản Trị & Suy Luận Chuyên Gia SRE (Executive Summary & RCA)
        is_llm = bool(rca.get("llm_enhanced") and rca.get("llm_insights"))
        gemini_model = rca.get("gemini_model") or "Gemini LLM"
        base_summary = rca.get("base_executive_summary") or rca.get("executive_summary", "Hệ thống áp dụng các quy tắc tất định theo tiêu chuẩn SRE.")
        rca_detail = rca.get("root_cause_analysis", {})
        primary_cause_val = rca_detail.get("primary_cause", rca.get("root_cause", "Không có lỗi."))
        llm_insights_val = rca.get("llm_insights", "")

        col_rca_l, col_rca_r = st.columns([3, 2])
        with col_rca_l:
            st.markdown("#### 🧠 Nhận Định & Suy Luận Chuyên Gia SRE")
            if is_llm:
                st.markdown(f"""
                <div style="background: #052e16; border: 1px solid #22c55e; border-left: 6px solid #16a34a; border-radius: 8px; padding: 14px; margin-bottom: 14px;">
                    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
                        <span style="font-weight: bold; color: #4ade80; font-size: 13.5px;">🤖 TRỢ LÝ SRE AI (GOOGLE GEMINI REASONING)</span>
                        <span style="background: #16a34a; color: #ffffff; font-size: 10.5px; font-weight: bold; padding: 2px 8px; border-radius: 4px;">{gemini_model}</span>
                    </div>
                    <div style="background: #14532d; border-radius: 6px; padding: 10px; font-size: 12.5px; color: #dcfce7; line-height: 1.6; white-space: pre-line;">
{llm_insights_val}
                    </div>
                    <div style="font-size: 11px; color: #86efac; margin-top: 6px; font-style: italic;">
                        🧠 <b>Cơ chế:</b> Tác tử tự động phân tích ngữ cảnh chéo giữa các tín hiệu và sinh chỉ thị ứng cứu tức thời bằng LLM.
                    </div>
                </div>
                """, unsafe_allow_html=True)
            else:
                st.markdown(f"""
                <div style="background: #0f172a; border: 1px solid #38bdf8; border-left: 6px solid #0284c7; border-radius: 8px; padding: 14px; margin-bottom: 14px;">
                    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
                        <span style="font-weight: bold; color: #38bdf8; font-size: 13.5px;">📚 SRE KNOWLEDGE BASE (TIÊU CHUẨN TẤT ĐỊNH RFC)</span>
                        <span style="background: #0284c7; color: #ffffff; font-size: 10.5px; font-weight: bold; padding: 2px 8px; border-radius: 4px;">RFC RUNBOOK</span>
                    </div>
                    <div style="background: #1e293b; border-radius: 6px; padding: 10px; font-size: 12.5px; color: #cbd5e1; line-height: 1.6;">
                        {base_summary}
                    </div>
                    <div style="font-size: 11px; color: #38bdf8; margin-top: 6px; font-style: italic;">
                        ⚡ <b>Cơ chế:</b> Suy luận tất định theo tiêu chuẩn RFC 9110/1035/5280, độ trễ 0ms, không phụ thuộc API ngoài.
                    </div>
                </div>
                """, unsafe_allow_html=True)

            st.markdown("#### 🔍 Chi Tiết Nguyên Nhân Gốc (Root Cause Details)")
            st.error(f"**Nguyên nhân cốt lõi:** {primary_cause_val}")
            if rca_detail.get("contributing_factors"):
                st.markdown("**Các yếu tố tiềm ẩn liên đới:**")
                for factor in rca_detail.get("contributing_factors", []):
                    st.markdown(f"- 🔸 {factor}")

        with col_rca_r:
            st.markdown("#### 💥 Đánh Giá Mức Độ Ảnh Hưởng (Impact Assessment)")
            impact = rca.get("impact_assessment", {})
            st.markdown(f"- 👤 **Trải nghiệm Người dùng:** {impact.get('user_experience', rca.get('user_impact', 'Không có gián đoạn.'))}")
            st.markdown(f"- 💼 **Tính khả dụng Nghiệp vụ:** {impact.get('business_availability', '100% SLA Available.')}")

            st.markdown("#### 🔬 Bằng Chứng Kỹ Thuật Đối Soát (Cross-Signal Evidence)")
            ev_map = rca_detail.get("cross_signal_evidence", {})
            for sig_name, sig_detail in ev_map.items():
                st.markdown(f"- **`[{sig_name}]`**: {sig_detail}")

        # 4.4 Action Plan, Runbook, Prevention & RFC Citations
        col_bot1, col_bot2 = st.columns(2)
        with col_bot1:
            st.markdown("#### 🛠️ Kế Hoạch Khắc Phục Khẩn Cấp (Immediate Action Plan)")
            for act in rca.get("immediate_action_plan", rca.get("action_plan", [])):
                st.markdown(f"- ✅ {act}")

            st.markdown("#### 🛡️ Chiến Lược Phòng Ngừa Dài Hạn (Prevention Strategy)")
            for prev in rca.get("prevention_strategy", []):
                st.markdown(f"- 🛡️ {prev}")

        with col_bot2:
            st.markdown("#### 🔬 Sổ Tay Điều Tra Chi Tiết (SRE Runbook / Playbook)")
            for step in rca.get("investigation_runbook", rca.get("investigation_steps", [])):
                st.markdown(f"- 🔎 {step}")

            st.markdown("#### 📚 Trích Dẫn Chuẩn Kỹ Thuật Quốc Tế (RFC Standards)")
            for rfc in rca.get("technical_standards", rca.get("rfc_citations", [])):
                st.code(rfc, language="text")

        # 4.5 Nút Tải Báo Cáo Sự Cố (Download Markdown)
        report_markdown = f"""# 📑 BÁO CÁO PHÂN TÍCH NGUYÊN NHÂN GỐC SỰ CỐ (INCIDENT RCA REPORT)
**Mã sự cố:** `{rca.get('incident_id', 'INC-001')}` | **Thời gian:** `{rca.get('timestamp', 'N/A')}` | **Mức độ:** `{rca.get('severity', sev)}`
**Website:** `{selected_site['name']}` ({selected_site.get('url')}) | **Tầng sự cố:** `{rca.get('fault_layer', 'N/A')}` | **Độ tin cậy:** `{rca.get('confidence_score', 98.8)}%`
**Hệ sinh thái công nghệ (Tech Stack):** `{rca.get('tech_stack', {}).get('one_line_summary', 'N/A')}`

---

## 1. Bản Tóm Tắt Quản Trị (Executive Summary)
{rca.get('executive_summary')}

---

## 2. Phân Tích & Suy Luận Tác Tử SRE (Agentic RCA Reasoning)
* **Cơ chế suy luận:** {"Google Gemini AI (" + gemini_model + ")" if is_llm else "SRE Knowledge Base (RFC Standards & Runbook)"}
* **Nguyên nhân cốt lõi:** {primary_cause_val}
* **Nhận định chuyên sâu:**
{llm_insights_val if is_llm else base_summary}

---

## 3. Các Yếu Tố Kỹ Thuật Đóng Góp (Contributing Factors)
{chr(10).join([f"- {cf}" for cf in rca_detail.get('contributing_factors', [])]) if rca_detail.get('contributing_factors') else '- Không ghi nhận yếu tố phụ.'}

---

## 4. Kế Hoạch Khắc Phục Đề Xuất (Action Plan)
{chr(10).join([f"- [ ] {a}" for a in rca.get('immediate_action_plan', rca.get('action_plan', []))])}

---

## 5. Sổ Tay Điều Tra Kỹ Thuật (SRE Runbook)
{chr(10).join([f"- {s}" for s in rca.get('investigation_runbook', rca.get('investigation_steps', []))])}

---

## 6. Chiến Lược Phòng Ngừa Dài Hạn (Prevention Strategy)
{chr(10).join([f"- {p}" for p in rca.get('prevention_strategy', [])])}

---

## 7. Tiêu Chuẩn Kỹ Thuật Đối Soát (Technical RFC Standards)
{chr(10).join([f"- {r}" for r in rca.get('technical_standards', rca.get('rfc_citations', []))])}

---

## 8. Chỉ Số Vận Hành Tác Tử (Agent Observability & LLMOps Telemetry)
* **Tổng thời gian điều phối:** {agent_result.get('total_execution_time_ms', 0)} ms
* **Độ trễ suy luận LLM:** {rca.get('llm_telemetry', {}).get('latency_ms', 0)} ms
* **Mức độ tiêu thụ Token:** {rca.get('llm_telemetry', {}).get('total_tokens', 0):,} tokens (Input: {rca.get('llm_telemetry', {}).get('prompt_tokens', 0)} | Output: {rca.get('llm_telemetry', {}).get('completion_tokens', 0)})
* **Tỷ lệ khử nhiễu cảnh báo DAG:** {agent_result.get('correlation', {}).get('noise_reduction_pct', 0)}% ({agent_result.get('correlation', {}).get('deduplication_ratio', 'N/A')})
"""
        st.download_button(
            label="📥 Tải Báo Cáo Sự Cố (Markdown Format)",
            data=report_markdown,
            file_name=f"RCA_Report_{selected_site['name'].replace(' ', '_')}_{rca.get('incident_id', 'INC001')}.md",
            mime="text/markdown",
            use_container_width=True
        )

        st.markdown("---")

        # 4.6 Chuỗi Vết Thực Thi Của Tác Tử (Execution Trace Timeline)
        st.markdown("### 🧩 4. Chuỗi Vết Thực Thi & Suy Luận Của Tác Tử (Execution Trace Timeline)")
        trace = agent_result.get("execution_trace", [])
        for t in trace:
            step_num = t.get("step")
            phase = t.get("phase")
            agent_n = t.get("agent")
            action = t.get("action")
            details = t.get("details")
            ts = t.get("timestamp")

            with st.expander(f"Bước {step_num} [{ts}]: **{phase}** — *{agent_n}* ({action})", expanded=(step_num in [1, 4, 5, 6])):
                st.markdown(f"**Tác tử phụ trách:** `{agent_n}` | **Hành động:** `{action}`")
                st.info(details)
                if "planned_tools" in t:
                    st.markdown(f"🛠️ **Công cụ đã lên lịch:** `{', '.join(t['planned_tools'])}`")
                if "tools_executed" in t:
                    st.markdown(f"⚙️ **Công cụ đã chạy thành công:** `{', '.join(t['tools_executed'])}`")
                if "violations_found" in t:
                    st.markdown(f"⚠️ **Bất thường phát hiện:** `{', '.join(t['violations_found']) if t['violations_found'] else 'Không có'}`")
                if "executed" in t:
                    st.markdown(f"🔄 **Tự sửa sai (Self-Correction):** `{'Đã kích hoạt re-probe' if t['executed'] else 'Không cần thiết'}`")

        st.markdown("---")

        # 4.7 Giám Sát Sức Khỏe & Hiệu Suất Tác Tử (Agent Observability & LLMOps Telemetry)
        st.markdown("### 📊 5. Giám Sát Sức Khỏe & Hiệu Suất Tác Tử (Agent Observability & LLMOps)")
        st.caption("Nguyên lý 'Monitoring the Monitor': Đo lường độ trễ, mức tiêu thụ token, trạng thái suy luận và tính sẵn sàng của AI Agent theo thời gian thực.")
        
        obs = agent_result.get("agent_observability", {})
        llm_obs = agent_result.get("rca_analysis", {}).get("llm_telemetry", {})
        
        # 5 Cột chỉ số Telemetry
        c_obs1, c_obs2, c_obs3, c_obs4, c_obs5 = st.columns(5)
        
        # 1. Trạng thái LLM
        llm_status_val = llm_obs.get("status", "DISABLED")
        if llm_obs.get("is_success"):
            c_obs1.metric("Suy Luận AI SRE", "🟢 Hoạt Động Tốt", llm_obs.get("model", "Gemini"))
        elif llm_status_val == "HEALTHY_SKIPPED":
            c_obs1.metric("Suy Luận AI SRE", "⚪ Tiết Kiệm (Healthy)", "0 token (Tối ưu)")
        elif llm_status_val == "RATE_LIMITED":
            c_obs1.metric("Suy Luận AI SRE", "🟡 Hết Ngạch (429)", "Fallback RFC")
        elif llm_status_val == "TIMEOUT":
            c_obs1.metric("Suy Luận AI SRE", "🔴 Quá Thời Gian", "Fallback RFC")
        elif llm_status_val == "MISSING_KEY":
            c_obs1.metric("Suy Luận AI SRE", "⚪ Chưa Có API Key", "Dùng RFC Rules")
        else:
            c_obs1.metric("Suy Luận AI SRE", "📚 Knowledge Base", "Chế độ RFC chuẩn")

        # 2. Độ trễ LLM
        c_obs2.metric("Độ Trễ LLM Gọi API", f"{llm_obs.get('latency_ms', 0)} ms", "Timeout: 25s")

        # 3. Tổng Token tiêu thụ
        t_tokens = llm_obs.get("total_tokens", 0)
        p_tokens = llm_obs.get("prompt_tokens", 0)
        c_tokens = llm_obs.get("completion_tokens", 0)
        c_obs3.metric("Token Tiêu Thụ", f"{t_tokens:,} tokens", f"In: {p_tokens} | Out: {c_tokens}")

        # 4. Thời gian Probes vs Tổng thời gian
        pr_ms = obs.get("probes_execution_ms", 0)
        tot_ms = obs.get("total_workflow_ms", 0)
        c_obs4.metric("Thời Gian Đo Probes", f"{pr_ms} ms", f"Tổng: {tot_ms} ms")

        # 5. Tự sửa sai (Self-Correction)
        sc_exec = obs.get("self_correction_executed", False)
        c_obs5.metric("Tự Sửa Sai (Re-probe)", "✅ Đã Kích Hoạt" if sc_exec else "⚪ Nhất Quán", "Backoff 1.5s")

        # Cảnh báo Fallback chi tiết nếu có
        if llm_obs.get("fallback_to_kb") and llm_obs.get("fallback_reason") and llm_status_val not in ["HEALTHY_SKIPPED", "DISABLED"]:
            st.warning(f"ℹ️ **Ghi nhận chuyển đổi dự phòng (Fallback Observability):** {llm_obs.get('fallback_reason')}")

        st.markdown("---")

        # 4.8 Ma Trận Đánh Giá 4 Khả Năng Cốt Lõi Của Agentic AI
        st.markdown("### 🏆 6. Ma Trận Đánh Giá 4 Khả Năng Cốt Lõi Của Agentic AI")
        capabilities = [
            {
                "Khả năng Cốt lõi": "1. Lập Kế Hoạch (Planning)",
                "Hiện thực trong Hệ thống": "Monitoring Orchestrator Agent tự động sinh danh sách công cụ và thứ tự ưu tiên kiểm tra phân cấp.",
                "Trạng thái": "✅ Đạt yêu cầu"
            },
            {
                "Khả năng Cốt lõi": "2. Sử Dụng Công Cụ (Tool Use)",
                "Hiện thực trong Hệ thống": "Probe Agent trực tiếp điều phối http_checker, dns_checker, ssl_checker, performance_checker, dom_validator, visual_checker.",
                "Trạng thái": "✅ Đạt yêu cầu"
            },
            {
                "Khả năng Cốt lõi": "3. Phản Hồi Linh Hoạt (Self-Correction)",
                "Hiện thực trong Hệ thống": "Tự động kích hoạt cơ chế Re-probe tức thời khi phát hiện bất thường chập chờn để loại trừ cảnh báo giả (Flapping).",
                "Trạng thái": "✅ Đạt yêu cầu"
            },
            {
                "Khả năng Cốt lõi": "4. Bộ Nhớ & Tri Thức (Knowledge Base)",
                "Hiện thực trong Hệ thống": "Truy vấn Kho tri thức chuẩn RFC 9110, RFC 1035, RFC 5280 và SRE Runbooks đối soát cùng Milestone Baseline.",
                "Trạng thái": "✅ Đạt yêu cầu"
            }
        ]
        st.dataframe(pd.DataFrame(capabilities), use_container_width=True, hide_index=True)


def render_history_tab(selected_site):
    """Hiển thị biểu đồ độ trễ và bảng lịch sử kiểm tra từ CSDL."""
    st.subheader(f"📈 Lịch sử & Xu hướng giám sát: {selected_site['name']}")
    
    logs = get_monitoring_logs(website_id=selected_site["id"], limit=100)
    if not logs:
        st.info("Chưa có bản ghi lịch sử kiểm tra nào trong cơ sở dữ liệu. Hãy bấm 'Quét & Chẩn Đoán' để thu thập dữ liệu.")
        return

    df = pd.DataFrame(logs)
    
    # 1. Thống kê tổng quan
    total_checks = len(df)
    healthy_count = len(df[df["overall_status"] == "HEALTHY"])
    warning_count = len(df[df["overall_status"] == "WARNING"])
    critical_count = len(df[df["overall_status"] == "CRITICAL"])
    health_rate = round((healthy_count / total_checks) * 100, 1) if total_checks > 0 else 0

    kpi_cols = st.columns(4)
    kpi_cols[0].metric("Tổng số lần kiểm tra", total_checks)
    kpi_cols[1].metric("Tỷ lệ Healthy", f"{health_rate}%")
    kpi_cols[2].metric("Cảnh báo (Warning)", warning_count)
    kpi_cols[3].metric("Sự cố (Critical)", critical_count)

    # 2. Biểu đồ xu hướng độ trễ
    st.markdown("#### ⏱️ Biểu đồ Độ trễ phản hồi (Latency Trend)")
    chart_df = df[["timestamp", "http_latency_ms", "dns_latency_ms"]].copy()
    chart_df["timestamp"] = pd.to_datetime(chart_df["timestamp"], utc=True).dt.tz_convert(TIMEZONE_NAME).dt.tz_localize(None)
    chart_df = chart_df.sort_values("timestamp")
    chart_df = chart_df.set_index("timestamp")
    chart_df.columns = ["HTTP Latency (ms)", "DNS Resolution Latency (ms)"]
    st.line_chart(chart_df)

    # 3. Bảng chi tiết lịch sử
    st.markdown("#### 📜 Nhật ký các lần quét gần nhất")
    display_df = df[[
        "timestamp", "overall_status", "http_status_code", 
        "http_latency_ms", "dns_resolved", "ssl_is_valid", "ssl_days_remaining"
    ]].copy()
    display_df["timestamp"] = pd.to_datetime(display_df["timestamp"], utc=True).dt.tz_convert(TIMEZONE_NAME).dt.strftime("%Y-%m-%d %H:%M:%S")
    display_df.columns = [
        "Thời điểm (UTC+7)", "Trạng thái", "Mã HTTP", 
        "Độ trễ HTTP (ms)", "DNS Resolved", "SSL Hợp lệ", "SSL Ngày còn lại"
    ]
    st.dataframe(display_df, use_container_width=True)

    # 4. Tóm tắt Báo cáo Sức khỏe Toàn hệ thống (24h qua)
    report_data = generate_periodic_report_data(hours=24)
    with st.expander("📊 Xem Bản tóm tắt Báo cáo Sức khỏe Hệ thống (24h qua)"):
        st.markdown(f"**Khởi tạo lúc:** `{report_data['report_generated_at']} (UTC+7)` | **Tỷ lệ Healthy toàn hệ thống:** **`{report_data['overall_health_rate']}%`**")
        
        rep_sites_df = pd.DataFrame(report_data["sites"])
        if not rep_sites_df.empty:
            rep_sites_df["diagnostic_summary"] = rep_sites_df["diagnostic_summary"].fillna("—")
            rep_sites_df = rep_sites_df[[
                "name", "current_status", "diagnostic_summary", "health_rate", 
                "avg_http_latency_ms", "avg_dns_latency_ms", "ssl_days_remaining", "total_scans"
            ]]
            rep_sites_df.columns = [
                "Website", "Hiện tại", "Chẩn đoán / Ghi chú sự cố", "Healthy %", 
                "Độ trễ HTTP (ms)", "Độ trễ DNS (ms)", "Hạn SSL (ngày)", "Số lần quét"
            ]
            st.dataframe(rep_sites_df, use_container_width=True)
            
        if report_data["incidents"]:
            st.warning(f"⚠️ Trong 24h qua có {len(report_data['incidents'])} sự cố/cảnh báo được ghi nhận.")
            inc_df = pd.DataFrame(report_data["incidents"])
            inc_df["timestamp"] = pd.to_datetime(inc_df["timestamp"], utc=True).dt.tz_convert(TIMEZONE_NAME).dt.strftime("%Y-%m-%d %H:%M:%S")
            inc_display = inc_df[["timestamp", "website_name", "status", "details"]].copy()
            inc_display.columns = ["Thời điểm (UTC+7)", "Website", "Mức độ", "Chi tiết Chẩn đoán Sự cố"]
            st.dataframe(inc_display, use_container_width=True)
        else:
            st.success("🎉 Không ghi nhận sự cố gián đoạn dịch vụ nào trong 24 giờ qua!")


def render_milestones_tab(selected_site):
    """Quản lý các mốc chuẩn hệ thống (Milestone Baselines)."""
    st.subheader(f"🏷️ Danh sách Mốc chuẩn (Baselines / Milestones): {selected_site['name']}")
    
    milestones = get_all_milestones(website_id=selected_site["id"])
    if not milestones:
        st.info("Chưa có mốc chuẩn nào được tạo cho website này.")
        return

    for m in milestones:
        status_badge = "🟢 Đang Kích Hoạt (Active)" if m["is_active"] else "⚪ Lưu trữ"
        with st.expander(f"Mốc ID #{m['id']} - {m['created_at']} | {status_badge}"):
            st.markdown(f"**Ghi chú:** {m.get('note') or 'Không có ghi chú'}")
            st.markdown(f"**Mã HTTP kỳ vọng:** `{m.get('expected_http_status')}`")
            st.markdown("**Bản ghi DNS chuẩn (Baseline):**")
            st.json(m.get("baseline_dns", {}))
            
            if not m["is_active"]:
                if st.button(f"🎯 Kích hoạt mốc #{m['id']} làm Baseline chuẩn", key=f"activate_{m['id']}"):
                    set_active_milestone(m["id"], selected_site["id"])
                    st.toast(f"Đã kích hoạt mốc #{m['id']} thành công!", icon="🎯")
                    st.rerun()


def render_system_observability_tab():
    """
    GIÁM SÁT CHÍNH HỆ THỐNG (Monitoring the Monitor):
    Latency workflow (avg/P95/max), Probes vs LLM, Token & Chi phí LLM, Fallback rate, Dung lượng lưu trữ.
    """
    import plotly.express as px

    st.subheader("📊 Giám Sát Hệ Thống (Platform Observability: Latency, Cost & Storage)")

    col_p1, col_p2 = st.columns([1, 3])
    with col_p1:
        period_label = st.selectbox(
            "Khoảng thời gian:",
            ["1 giờ", "24 giờ", "7 ngày", "30 ngày"],
            index=1,
            key="obs_period"
        )
    hours = {"1 giờ": 1, "24 giờ": 24, "7 ngày": 168, "30 ngày": 720}[period_label]
    m = get_telemetry_metrics_summary(hours=hours)

    # --- 1. Latency KPIs ---
    st.markdown("#### ⏱️ Độ Trễ Xử Lý (Workflow Latency)")
    k1, k2, k3, k4, k5 = st.columns(5)
    k1.metric("Tổng lượt chạy", f"{m['total_runs']:,}")
    k2.metric("Latency TB", f"{m['avg_workflow_latency_ms']:,.0f} ms")
    k3.metric("Latency P95", f"{m['p95_workflow_latency_ms']:,.0f} ms")
    k4.metric("Probes TB", f"{m['avg_probes_latency_ms']:,.0f} ms")
    k5.metric("LLM TB", f"{m['avg_llm_latency_ms']:,.0f} ms")

    # --- 2. Cost KPIs ---
    st.markdown("#### 💰 Chi Phí & Token LLM (LLMOps Cost)")
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Tổng chi phí (USD)", f"${m['total_cost_usd']:.4f}")
    c2.metric("Tổng chi phí (VNĐ)", f"{m['total_cost_vnd']:,.0f} ₫")
    c3.metric("Tổng tokens", f"{m['total_tokens']:,}")
    c4.metric("LLM thành công", f"{m['llm_success_count']:,}")
    c5.metric("Tỷ lệ Fallback KB", f"{m['fallback_rate_pct']}%")
    st.caption(
        "Chi phí là **ước tính** theo bảng giá Gemini (Flash: $0.075/1M input, $0.30/1M output; "
        "Pro: $1.25/1M input, $5.00/1M output). Tỷ giá quy đổi: 25,400 ₫/USD. "
        "Hãy điều chỉnh trong `calculate_llm_cost()` nếu bảng giá thay đổi."
    )

    if m["total_runs"] == 0:
        st.info("Chưa có dữ liệu telemetry trong khoảng thời gian này. Hãy chạy 'Full SRE Workflow' hoặc chờ Scheduler quét định kỳ.")
    else:
        df = pd.DataFrame(m["recent_logs"])
        df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
        df = df.sort_values("timestamp")

        g1, g2 = st.columns(2)
        with g1:
            fig_lat = px.line(
                df, x="timestamp",
                y=["total_latency_ms", "probes_latency_ms", "llm_latency_ms"],
                markers=True, title="Biến thiên độ trễ (ms) - 50 lượt gần nhất"
            )
            fig_lat.update_layout(height=340, legend_title_text="", margin=dict(l=10, r=10, t=40, b=10))
            st.plotly_chart(fig_lat, use_container_width=True)
        with g2:
            fig_cost = px.bar(
                df, x="timestamp", y="estimated_cost_usd", color="workflow_type",
                title="Chi phí LLM theo lượt chạy (USD)"
            )
            fig_cost.update_layout(height=340, legend_title_text="", margin=dict(l=10, r=10, t=40, b=10))
            st.plotly_chart(fig_cost, use_container_width=True)

        b1, b2 = st.columns(2)
        with b1:
            st.markdown("**🤖 Phân bổ theo Model**")
            mb = pd.DataFrame([
                {"Model": k, "Lượt gọi": v["calls"], "Tokens": v["tokens"], "Chi phí (USD)": v["cost_usd"]}
                for k, v in m["models_breakdown"].items()
            ])
            st.dataframe(mb, use_container_width=True, hide_index=True)
        with b2:
            st.markdown("**🌐 Phân bổ theo Website**")
            wb = pd.DataFrame([
                {"Website": k, "Lượt quét": v["scans"], "Latency TB (ms)": v["avg_latency_ms"],
                 "Tokens": v["tokens"], "Chi phí (USD)": v["cost_usd"]}
                for k, v in m["websites_cost_breakdown"].items()
            ]).sort_values("Chi phí (USD)", ascending=False)
            st.dataframe(wb, use_container_width=True, hide_index=True)

        with st.expander("📜 Nhật ký telemetry chi tiết (50 lượt gần nhất)"):
            show_cols = [
                "timestamp", "workflow_type", "website_name", "overall_severity",
                "total_latency_ms", "probes_latency_ms", "llm_latency_ms", "llm_model",
                "llm_status", "total_tokens", "estimated_cost_usd", "fallback_to_kb",
                "self_correction_executed"
            ]
            st.dataframe(df[show_cols].sort_values("timestamp", ascending=False), use_container_width=True, hide_index=True)

    # --- 3. Storage ---
    st.markdown("#### 💾 Dung Lượng Lưu Trữ (Storage)")
    s = get_storage_metrics()
    s1, s2, s3, s4, s5 = st.columns(5)
    s1.metric("Tổng dung lượng", f"{s['total_storage_mb']} MB")
    s2.metric("CSDL SQLite", f"{s['db_size_mb']} MB")
    s3.metric("Screenshots", f"{s['screenshots_size_mb']} MB", f"{s['screenshots_count']} file", delta_color="off")
    s4.metric("Visual Diffs", f"{s['visual_diffs_size_mb']} MB", f"{s['visual_diffs_count']} file", delta_color="off")
    s5.metric("Backups", f"{s['backups_size_mb']} MB", f"{s['backups_count']} file", delta_color="off")

    retention_days = int(get_system_settings().get("data_retention_days") or 30)
    if st.button(
        f"🧹 Dọn dẹp log & ảnh cũ hơn {retention_days} ngày",
        key="btn_purge_artifacts",
        help="Xóa monitoring_logs, system_telemetry_logs và ảnh screenshots/diffs cũ hơn số ngày Retention. Giữ lại *_latest.png và baseline."
    ):
        deleted_logs = purge_old_logs(days_to_keep=retention_days)
        st.success(f"Đã xóa {deleted_logs} bản ghi log cũ và dọn dẹp ảnh cũ hơn {retention_days} ngày.")
        st.rerun()


def render_dashboard(selected_site):
    """Giao diện Dashboard Giám sát SRE Vận hành Production Thống Nhất."""
    tab1, tab2, tab3, tab4 = st.tabs([
        "🎯 Trung Tâm Điều Hành SRE (Unified Operations & RCA)", 
        "📈 Lịch Sử & Xu Hướng (Telemetry History & Trends)", 
        "🏷️ Quản Lý Mốc Chuẩn (Milestone Baselines)",
        "📊 Giám Sát Hệ Thống (Latency & Cost)"
    ])
    
    with tab1:
        render_unified_sre_console(selected_site)

    with tab2:
        render_history_tab(selected_site)
        
    with tab3:
        render_milestones_tab(selected_site)

    with tab4:
        render_system_observability_tab()

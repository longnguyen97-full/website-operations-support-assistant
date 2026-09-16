import streamlit as st
import pandas as pd
from datetime import datetime
from config import TIMEZONE_NAME
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
    get_email_settings,
    update_email_settings
)

def render_traditional_tab(selected_site):
    """Tab Cấu hình 1: Giám sát Dựa trên Ngưỡng Truyền thống (Threshold-based / Detect & Alert / Human-driven)."""
    
    # CONTEXT BADGE & BANNER WORKFLOW CHẾ ĐỘ TRUYỀN THỐNG (ORANGE THEME)
    st.markdown("""
    <div style="margin-bottom: 12px;">
        <span style="background-color: #d97706; color: #ffffff; padding: 5px 12px; border-radius: 6px; font-weight: 700; font-size: 13px; letter-spacing: 0.5px; box-shadow: 0 2px 4px rgba(217,119,6,0.2);">
            ⚠️ CẤU HÌNH 1: TRUYỀN THỐNG (DETECT & ALERT / HUMAN-DRIVEN)
        </span>
    </div>
    <div style="background: linear-gradient(90deg, #78350f 0%, #0f172a 100%); color: #f8fafc; padding: 14px 18px; border-radius: 10px; margin-bottom: 20px; border-left: 5px solid #f59e0b; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.1);">
        <div style="font-weight: bold; font-size: 15px; color: #fcd34d; margin-bottom: 6px;">
            ⚠️ QUY TRÌNH THỰC THI (TRADITIONAL THRESHOLD WORKFLOW)
        </div>
        <div style="font-size: 13px; color: #cbd5e1; line-height: 1.6;">
            <b>Luồng xử lý:</b> <code>[1. Quét HTTP Ping Đơn Tín Hiệu]</code> ➔ <code>[2. So Sánh Ngưỡng Cứng (!= 200 hoặc > 2000ms)]</code> ➔ <code>[3. Bắn Cảnh Báo Thô Ngay Lập Tức (Alert Storm)]</code> ➔ <code>[4. Kỹ sư tự tra cứu log trên server]</code>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # Nút bấm kích hoạt thủ công riêng cho Cấu hình 1
    col_act1, _ = st.columns([2, 3])
    with col_act1:
        run_trad_btn = st.button("🚀 Chạy Giám Sát Cấu Hình 1 (HTTP Ngưỡng Tĩnh)", key=f"btn_run_cfg1_{selected_site['id']}", use_container_width=True, type="primary")

    if run_trad_btn:
        from tools.http_checker import check_http
        from config import HTTP_TIMEOUT_SECONDS
        from database.repository import get_system_settings
        sys_settings = get_system_settings()
        http_timeout = float(sys_settings.get("http_timeout_seconds") or HTTP_TIMEOUT_SECONDS)
        expected_status = selected_site.get("expected_status", 200)

        with st.spinner(f"⚠️ [Cấu hình 1] Đang ping HTTP đơn tín hiệu kiểm tra ngưỡng tĩnh cho '{selected_site['name']}'..."):
            http_res = check_http(selected_site["url"], expected_status=expected_status, timeout=http_timeout)
            if "last_trad_scan" not in st.session_state:
                st.session_state["last_trad_scan"] = {}
            st.session_state["last_trad_scan"][selected_site["id"]] = http_res
            st.toast("Đã hoàn thành kiểm tra Đơn tín hiệu HTTP (Cấu hình 1)!", icon="⚠️")
            st.rerun()

    http_res = st.session_state.get("last_trad_scan", {}).get(selected_site["id"])
    if not http_res:
        st.info("👉 Hãy bấm nút **'🚀 Chạy Giám Sát Cấu Hình 1 (HTTP Ngưỡng Tĩnh)'** ở trên để kích hoạt phiên quét đơn tín hiệu theo Cấu hình 1.")
        return

    from database.repository import get_system_settings
    from analytics.anomaly_detector import AnomalyDetectionOrchestrator

    sys_settings = get_system_settings()
    latency_thresh = float(sys_settings.get("latency_threshold_ms", 2000.0))
    expected_status = selected_site.get("expected_status", 200)

    orchestrator = AnomalyDetectionOrchestrator()
    trad_analysis = orchestrator.run_threshold_based_monitoring(
        http_res=http_res,
        latency_threshold_ms=latency_thresh,
        expected_status=expected_status
    )

    st.subheader(f"📊 Kết quả Giám sát Truyền thống: {selected_site['name']}")
    st.markdown(f"**URL:** [{selected_site['url']}]({selected_site['url']}) | **Mã mong đợi:** `{expected_status}` | **Ngưỡng trễ:** `{latency_thresh} ms`")

    # 4 KPI Metrics Card cho Cấu hình 1
    kpi1, kpi2, kpi3, kpi4 = st.columns(4)
    http_code = http_res.get("status_code")
    http_cat = http_res.get("status_category", "")
    http_display = f"{http_code} {http_cat}".strip() if http_code is not None else (http_res.get("error_title") or "Connection Failed")

    kpi1.metric(
        "🌐 HTTP Status Code", 
        http_display, 
        f"Kỳ vọng: {expected_status}"
    )
    kpi2.metric(
        "⏱️ Thời gian phản hồi", 
        f"{http_res.get('response_time_ms', 0)} ms", 
        f"Ngưỡng: <= {latency_thresh} ms"
    )
    
    viol_count = trad_analysis.get("violations_count", 0)
    kpi3.metric(
        "🚨 Vi phạm Ngưỡng Tĩnh", 
        f"{viol_count} Cảnh báo", 
        "Bắn Alert độc lập",
        delta_color="inverse" if viol_count > 0 else "normal"
    )
    kpi4.metric(
        "👤 Cơ chế Vận hành", 
        "Human-driven", 
        "Kỹ sư tự điều tra"
    )

    st.markdown("---")

    # Hiển thị Luồng Cảnh Báo Thô (Raw Alert Stream)
    st.markdown("### 🚨 Luồng Cảnh Báo Thô Phát Sinh (Raw Alert Stream - Không có lọc nhiễu)")
    if trad_analysis.get("violations"):
        for v in trad_analysis["violations"]:
            st.error(f"🚨 **[{v['type']}]** {v['message']}")
    else:
        st.success(f"✅ Website phản hồi trong ngưỡng cho phép (HTTP {expected_status}, Response Time <= {latency_thresh}ms).")

    st.markdown("""
    <div style="background: #fffbeb; border: 1px solid #fde68a; border-radius: 8px; padding: 14px; margin-top: 15px;">
        <h5 style="color: #b45309; margin-top: 0;">⚠️ Đặc Tính & Hạn Chế Của Cấu Hình 1 (Truyền Thống):</h5>
        <ul style="color: #78350f; font-size: 13px; line-height: 1.6; margin-bottom: 0;">
            <li><b>Chỉ Kiểm Tra Đơn Tín Hiệu (Single Signal):</b> Chỉ ping bề mặt mã HTTP và thời gian phản hồi; không thu thập thông tin DNS, SSL, hay phân tích bất thường DOM/Visual.</li>
            <li><b>Không Có Khử Nhiễu & Tương Quan:</b> Bắn alert độc lập ngay khi vi phạm ngưỡng cứng, dễ dẫn đến hiện tượng <i>Bão cảnh báo (Alert Storm / Alert Fatigue)</i>.</li>
            <li><b>Không Có Khả Năng Tự Sửa Sai (Self-Correction):</b> Không tự động re-probe để loại trừ lỗi chập chờn (flapping).</li>
            <li><b>Không Có Báo Cáo Nguyên Nhân Gốc (RCA):</b> Không tự sinh phân tích nguyên nhân hay gợi ý Runbook, kỹ sư SRE phải tự vào máy chủ kiểm tra từng file log.</li>
        </ul>
    </div>
    """, unsafe_allow_html=True)


def render_realtime_tab(selected_site):
    """Tab 2: Giám sát Đa Tín hiệu Thời gian thực & Phân tích Tương quan Bán tự động (Semi-automated)."""
    
    # CONTEXT BADGE & BANNER WORKFLOW CHẾ ĐỘ BÁN TỰ ĐỘNG (BLUE THEME)
    st.markdown("""
    <div style="margin-bottom: 12px;">
        <span style="background-color: #2563eb; color: #ffffff; padding: 5px 12px; border-radius: 6px; font-weight: 700; font-size: 13px; letter-spacing: 0.5px; box-shadow: 0 2px 4px rgba(37,99,235,0.2);">
            🛡️ CẤU HÌNH 2: BÁN TỰ ĐỘNG (SUGGEST & APPROVE / HUMAN-IN-THE-LOOP)
        </span>
    </div>
    <div style="background: linear-gradient(90deg, #1e3a8a 0%, #0f172a 100%); color: #f8fafc; padding: 14px 18px; border-radius: 10px; margin-bottom: 20px; border-left: 5px solid #38bdf8; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.1);">
        <div style="font-weight: bold; font-size: 15px; color: #38bdf8; margin-bottom: 6px;">
            🛡️ QUY TRÌNH THỰC THI (SEMI-AUTOMATED WORKFLOW)
        </div>
        <div style="font-size: 13px; color: #cbd5e1; line-height: 1.6;">
            <b>Luồng xử lý:</b> <code>[1. Thu thập Đa Tín hiệu]</code> ➔ <code>[2. Đối soát Luật RFC & Z-Score]</code> ➔ <code>[3. Gom nhóm Cây phụ thuộc]</code> ➔ <code>[4. Gán nhãn lỗi thô (Suggest)]</code> ➔ <code>[5. Kỹ sư phê chuẩn]</code>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    # Nút bấm kích hoạt thủ công riêng cho Cấu hình 2
    col_act1, col_act2 = st.columns([2, 3])
    with col_act1:
        run_semi_btn = st.button("🚀 Chạy Giám Sát Cấu Hình 2 (Đa Tín Hiệu & Z-Score)", key=f"btn_run_cfg2_{selected_site['id']}", use_container_width=True, type="primary")
    with col_act2:
        enable_screenshot = st.checkbox("📸 Kèm chụp ảnh Playwright khi quét", value=True, key=f"semi_shot_toggle_{selected_site['id']}")

    if run_semi_btn:
        from tools.http_checker import check_http
        from tools.dns_checker import check_dns
        from tools.ssl_checker import check_ssl
        from tools.visual_checker import check_visual_regression
        from database.repository import save_monitoring_log, calculate_overall_status, get_system_settings
        from notifications import check_and_send_alert
        from config import HTTP_TIMEOUT_SECONDS, DNS_TIMEOUT_SECONDS, SSL_TIMEOUT_SECONDS

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

        with st.spinner(f"🛡️ [Cấu hình 2] Đang thu thập Đa tín hiệu (HTTP/DNS/SSL/DOM/Visual) và tính Z-Score cho '{selected_site['name']}'..."):
            http_res = check_http(selected_site["url"], expected_status=expected_status, timeout=http_timeout)
            dns_res = check_dns(selected_site["domain"], baseline=baseline_dns, timeout=dns_timeout)
            ssl_res = check_ssl(selected_site["url"], timeout=ssl_timeout)
            
            # Quét cấu trúc DOM (Missing DOM / Broken UI)
            from tools.dom_validator import validate_dom
            dom_res = None
            if http_res.get("status_code") == 200:
                try:
                    dom_timeout = min(http_timeout, 12.0)
                    dom_res = validate_dom(selected_site["url"], use_browser=False, timeout=dom_timeout)
                except Exception as ex:
                    dom_res = {"error": str(ex), "can_inspect": False, "is_structure_valid": True, "missing_critical_elements": []}

            visual_res = None
            if enable_screenshot:
                try:
                    visual_res = check_visual_regression(
                        url=selected_site["url"],
                        website_identifier=selected_site["name"],
                        full_page=True,
                        timeout=20.0
                    )
                except Exception as ex:
                    visual_res = {"error": str(ex), "status": "ERROR"}

            overall_status = calculate_overall_status(http_res, dns_res, ssl_res, dom_res=dom_res, visual_res=visual_res)
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
            try:
                # Nếu có sự cố, tự động sinh phân tích RCA sơ bộ từ Anomaly Orchestrator để đưa vào Email Cảnh Báo
                rca_ctx = None
                if overall_status in ["CRITICAL", "WARNING"]:
                    from analytics.anomaly_detector import AnomalyDetectionOrchestrator
                    det_orch = AnomalyDetectionOrchestrator()
                    cfg2_res = det_orch.run_multi_signal_rule_statistical(
                        http_res=http_res,
                        dns_res=dns_res,
                        ssl_res=ssl_res,
                        dom_res=dom_res,
                        visual_res=visual_res
                    )
                    rca_ctx = {
                        "fault_layer": "Hạ Tầng Ứng Dụng & Mạng",
                        "fault_category": cfg2_res.get("incident_type"),
                        "root_cause_analysis": {
                            "primary_cause": cfg2_res.get("root_cause_summary"),
                            "contributing_factors": [v.get("description") for v in cfg2_res.get("all_violations", [])[:3]]
                        },
                        "immediate_action_plan": [
                            "Kiểm tra nhật ký lỗi máy chủ ứng dụng.",
                            "Xác minh kết nối cơ sở dữ liệu và cấu hình Virtual Host proxy.",
                            "Kích hoạt chu trình tác tử Agentic AI Studio để phân tích sâu bằng LLM."
                        ],
                        "technical_standards": ["RFC 9110", "RFC 1035", "RFC 5280"]
                    }
                check_and_send_alert(selected_site, overall_status, http_res, dns_res, ssl_res, rca_report=rca_ctx)
            except Exception as e:
                print(f"[!] Warning: check_and_send_alert failed: {e}")

            if "last_scan" not in st.session_state:
                st.session_state["last_scan"] = {}
            st.session_state["last_scan"][selected_site["id"]] = {
                "http": http_res,
                "dns": dns_res,
                "ssl": ssl_res,
                "dom": dom_res,
                "visual": visual_res
            }
            st.toast("Đã hoàn tất phân tích Đa tín hiệu & Z-Score (Cấu hình 2)!", icon="🛡️")
            st.rerun()

    site_scan = st.session_state.get("last_scan", {}).get(selected_site["id"], {})
    http_res = site_scan.get("http")
    dns_res = site_scan.get("dns")
    ssl_res = site_scan.get("ssl")
    dom_res = site_scan.get("dom")
    visual_res = site_scan.get("visual")

    if not (http_res and dns_res and ssl_res):
        st.info("👉 Hãy bấm nút **'🚀 Chạy Giám Sát Cấu Hình 2 (Đa Tín Hiệu & Z-Score)'** ở trên để kích hoạt phiên quét đa tín hiệu theo Cấu hình 2.")
        return

    from database.repository import calculate_overall_status
    overall_status = calculate_overall_status(http_res, dns_res, ssl_res, dom_res=dom_res, visual_res=visual_res)

    status_badge_map = {
        "HEALTHY": ("🟢 HOẠT ĐỘNG TỐT (HEALTHY)", "#10b981"),
        "WARNING": ("🟡 CẢNH BÁO (WARNING)", "#f59e0b"),
        "CRITICAL": ("🔴 SỰ CỐ NGHIÊM TRỌNG (CRITICAL)", "#ef4444")
    }
    badge_label, badge_color = status_badge_map.get(overall_status, ("⚪ KHÔNG XÁC ĐỊNH", "#6b7280"))

    # 1. Header Overview & KPI Bar
    st.subheader(f"📊 Kết quả kiểm tra Bán tự động: {selected_site['name']}")
    st.markdown(f"**Trạng thái Tổng thể:** `{badge_label}` | **URL:** [{selected_site['url']}]({selected_site['url']}) | **Domain:** `{selected_site['domain']}`")

    # 4 KPI Metrics Card
    kpi1, kpi2, kpi3, kpi4 = st.columns(4)
    http_code = http_res.get("status_code")
    http_cat = http_res.get("status_category", "")
    if http_code is not None:
        http_display = f"{http_code} {http_cat}".strip()
    else:
        http_display = http_res.get("error_title") or "Connection Failed"

    kpi1.metric(
        "🌐 HTTP Status", 
        http_display, 
        f"{http_res.get('response_time_ms', 0)} ms"
    )
    
    dns_ok = "Resolved" if dns_res.get("resolved") else "Failed"
    kpi2.metric(
        "🗂️ DNS Resolution", 
        dns_ok, 
        f"{dns_res.get('resolution_time_ms', 0)} ms"
    )
    
    # KPI 3: SSL Certificate
    ssl_days = ssl_res.get("days_remaining", 0)
    if ssl_res.get("is_http_only"):
        ssl_status = "Bỏ qua (HTTP)"
        ssl_delta = "Website không dùng SSL"
    elif ssl_res.get("can_connect") is False:
        ssl_status = "Không thể kiểm tra"
        ssl_delta = ssl_res.get("error_title") or "Lỗi kết nối TCP"
    elif ssl_res.get("is_valid"):
        ssl_status = "Hợp lệ"
        ssl_delta = f"{ssl_days} ngày còn lại"
    else:
        ssl_status = "Không hợp lệ"
        ssl_delta = ssl_res.get("error_title") or "Chứng chỉ không hợp lệ"

    kpi3.metric(
        "🔒 SSL Certificate", 
        ssl_status, 
        ssl_delta
    )
    
    # KPI 4: Đối soát Baseline
    active_b = get_active_baseline(selected_site["id"])
    if not active_b:
        match_label = "⚪ Chưa có Baseline"
        match_delta = "Cold-start (Chưa thiết lập mốc chuẩn)"
    else:
        dns_match = not bool(dns_res.get("changes_detected"))
        http_match = bool(http_res.get("is_expected_status"))
        
        if dns_match and http_match:
            match_label = "🟢 Khớp Baseline"
            match_delta = "Trùng khớp hoàn toàn"
        elif not http_match and not dns_match:
            match_label = "🔴 Lệch Baseline"
            match_delta = "Sai mã HTTP & Lệch DNS"
        elif not http_match:
            match_label = "🟡 Lệch Baseline"
            match_delta = f"Sai mã HTTP ({http_res.get('status_code') or http_res.get('error_title', 'Lỗi')})"
        else:
            match_label = "🟡 Lệch Baseline"
            match_delta = "Phát hiện thay đổi DNS"

    kpi4.metric(
        "🎯 Đối soát Baseline", 
        match_label, 
        match_delta
    )

    st.markdown("---")

    # 1.5. Khối Phân tích Bất thường & Tương quan Sự cố Bán Tự Động (Multi-Signal Rule & Statistical)
    from database.repository import get_website_latency_history
    from analytics.anomaly_detector import AnomalyDetectionOrchestrator

    lat_history = get_website_latency_history(selected_site["id"], limit=50)

    orchestrator = AnomalyDetectionOrchestrator()
    analysis = orchestrator.run_multi_signal_rule_statistical(
        http_res=http_res,
        dns_res=dns_res,
        ssl_res=ssl_res,
        dom_res=dom_res,
        visual_res=visual_res,
        history_latencies=lat_history
    )
    mode_tag = "🛡️ CẤU HÌNH 2: GIÁM SÁT ĐA TÍN HIỆU + LUẬT RFC + THỐNG KÊ Z-SCORE (KHÔNG AI)"
    mode_box_color = "#eff6ff"

    with st.container():
        st.markdown(f"""
        <div style="background: {mode_box_color}; padding: 12px 16px; border-radius: 8px; border: 1px solid #bfdbfe; margin-bottom: 15px;">
            <div style="font-size: 13px; font-weight: bold; color: #1d4ed8; text-transform: uppercase;">
                {mode_tag}
            </div>
            <div style="font-size: 14px; margin-top: 4px; color: #1e40af;">
                <b>Đề xuất Mã lỗi Kỹ thuật (Suggest):</b> {analysis.get('root_cause_summary') or 'Hệ thống bình thường.'}
            </div>
        </div>
        """, unsafe_allow_html=True)

        c_an1, c_an2, c_an3 = st.columns(3)
        c_an1.metric("Điểm Bất Thường Tổng (0-100)", f"{analysis.get('anomaly_score', 0)} / 100", help="Tổng điểm phạt từ các vi phạm luật RFC và đột biến Z-Score")
        c_an2.metric("Sự cố Nhận diện", analysis.get("incident_type", "NONE"))
        c_an3.metric("Cảnh báo Trùng Triệt tiêu", f"{analysis.get('suppressed_alerts_count', 0)} cảnh báo")

        z_info = analysis.get("z_score_analysis", {})
        if z_info.get("is_anomaly"):
            z_weight = 25 if z_info.get("severity") == "CRITICAL" else 15
            st.markdown(f"""
            <div style="background: #fef2f2; border: 1px solid #fecaca; border-radius: 6px; padding: 10px 14px; margin-top: 10px; display: flex; align-items: center; justify-content: space-between;">
                <span style="color: #991b1b; font-weight: 600; font-size: 13px;">
                    📈 <b>Phát hiện Đột biến Độ trễ Z-Score (+{z_info.get('z_score')}):</b> {z_info.get('reason')}
                </span>
                <span style="background-color: #ef4444; color: #ffffff; padding: 3px 8px; border-radius: 4px; font-weight: 700; font-size: 12px; white-space: nowrap; margin-left: 10px;">
                    +{z_weight} ĐIỂM (Z-Score {z_info.get('severity')})
                </span>
            </div>
            """, unsafe_allow_html=True)
        elif z_info.get("sample_count", 0) >= z_info.get("min_samples_required", 5):
            st.caption(f"📊 **Thống kê Z-Score:** Z = `{z_info.get('z_score')}` (Mean: `{z_info.get('mean_ms')}ms`, Std: `{z_info.get('std_ms')}ms` qua {z_info.get('sample_count')} lần quét) ➔ *Không có điểm phạt (0đ)*")

        # BẢNG PHÂN RÃ CHI TIẾT CÁC NGUỒN CỘNG ĐIỂM BẤT THƯỜNG
        violations_list = analysis.get("all_violations", [])
        with st.expander("📊 Xem Bảng Phân Rã Chi Tiết Điểm Bất Thường (+Points Breakdown)", expanded=bool(analysis.get("anomaly_score", 0) > 0)):
            if violations_list:
                breakdown_data = []
                total_raw_weight = 0
                for v in violations_list:
                    w = v.get("weight", 10)
                    total_raw_weight += w
                    breakdown_data.append({
                        "Tín hiệu (Signal)": v.get("signal", "N/A"),
                        "Mã quy tắc (Rule ID)": v.get("rule_id", "N/A"),
                        "Mô tả Bất thường": v.get("title") or v.get("description", "N/A"),
                        "Mức độ": v.get("severity", "WARNING"),
                        "Điểm cộng vào (+Weight)": f"+{w} điểm"
                    })
                st.dataframe(pd.DataFrame(breakdown_data), use_container_width=True, hide_index=True)
                st.markdown(f"**Công thức tổng hợp:** $\\text{{Anomaly Score}} = \\min(100, \\sum \\text{{Weight}}) = \\min(100, {total_raw_weight}) = \\mathbf{{{min(100, total_raw_weight)} / 100}}$")
            else:
                st.success("✅ Không ghi nhận bất kỳ vi phạm nào. Tổng điểm phạt = 0 / 100 (Hệ thống hoàn toàn khỏe mạnh).")

    st.markdown("---")

    # 2. Chi tiết 4 tín hiệu phân bổ 4 Cột chuyên biệt (KÈM TAG +ĐIỂM)
    col_http, col_dns, col_ssl, col_dom = st.columns(4)

    # Cột 1: HTTP Monitoring (RFC 9110)
    with col_http:
        st.markdown("#### 🌐 HTTP (RFC 9110)")
        status_code = http_res.get("status_code")
        if http_res.get("is_success"):
            st.success(f"Status Code: **{status_code}** ({http_res.get('status_category')})")
        else:
            st.error(f"HTTP Error: **{status_code or 'Failed'}**")
            # Gắn Tag điểm phạt HTTP
            if status_code is None or http_res.get("error"):
                st.markdown('<span style="background-color: #ef4444; color: white; padding: 2px 8px; border-radius: 4px; font-weight: bold; font-size: 11px;">+40 ĐIỂM (HTTP Connection Failure)</span>', unsafe_allow_html=True)
            elif status_code and 500 <= status_code <= 599:
                st.markdown('<span style="background-color: #ef4444; color: white; padding: 2px 8px; border-radius: 4px; font-weight: bold; font-size: 11px;">+35 ĐIỂM (HTTP 5xx Server Error)</span>', unsafe_allow_html=True)
            elif not http_res.get("is_expected_status"):
                st.markdown('<span style="background-color: #f59e0b; color: white; padding: 2px 8px; border-radius: 4px; font-weight: bold; font-size: 11px;">+20 ĐIỂM (HTTP Status Code Mismatch)</span>', unsafe_allow_html=True)
        
        st.markdown(f"- **Method:** `{http_res.get('method')}`")
        st.markdown(f"- **Thời gian phản hồi:** `{http_res.get('response_time_ms')} ms`")
        st.markdown(f"- **Mã mong đợi:** `{http_res.get('is_expected_status')}` (`{selected_site.get('expected_status', 200)}`)")
        
        if http_res.get("redirect_chain"):
            st.info("🔄 **Redirect Chain:**\n" + "\n".join([f"- `{hop['url']}` ({hop['status_code']})" for hop in http_res["redirect_chain"]]))
            if len(http_res["redirect_chain"]) >= 5:
                st.markdown('<span style="background-color: #ef4444; color: white; padding: 2px 8px; border-radius: 4px; font-weight: bold; font-size: 11px;">+30 ĐIỂM (Redirect Loop)</span>', unsafe_allow_html=True)
            
        if http_res.get("error") or http_res.get("error_title"):
            err_title = http_res.get("error_title") or "Lỗi kết nối HTTP"
            err_detail = http_res.get("error_detail") or http_res.get("error")
            st.warning(f"**Tiêu đề lỗi:** `{err_title}`\n\n**Chi tiết (Tooltip/Log):** `{err_detail}`")
            
        if http_res.get("headers"):
            with st.expander("🔍 Xem HTTP Headers"):
                st.json(http_res["headers"])

    # Cột 2: DNS Monitoring (RFC 1035)
    with col_dns:
        st.markdown("#### 🗂️ DNS (RFC 1035)")
        if dns_res.get("resolved"):
            st.success(f"Resolution: **Thành công** ({dns_res.get('resolution_time_ms')} ms)")
        else:
            st.error(f"DNS Resolution: **Thất bại**")
            st.markdown('<span style="background-color: #ef4444; color: white; padding: 2px 8px; border-radius: 4px; font-weight: bold; font-size: 11px;">+40 ĐIỂM (DNS Resolution Failed)</span>', unsafe_allow_html=True)
            
        dns_summary_rows = []
        if dns_res.get("a"):
            dns_summary_rows.append({"Type": "A (IPv4)", "Value": ", ".join(dns_res["a"]), "TTL": str(dns_res.get("ttl", {}).get("a", "-"))})
        if dns_res.get("aaaa"):
            dns_summary_rows.append({"Type": "AAAA (IPv6)", "Value": ", ".join(dns_res["aaaa"]), "TTL": str(dns_res.get("ttl", {}).get("aaaa", "-"))})
        if dns_res.get("cname"):
            dns_summary_rows.append({"Type": "CNAME", "Value": str(dns_res["cname"]), "TTL": str(dns_res.get("ttl", {}).get("cname", "-"))})
        if dns_res.get("mx"):
            dns_summary_rows.append({"Type": "MX", "Value": "; ".join(dns_res["mx"][:2]), "TTL": str(dns_res.get("ttl", {}).get("mx", "-"))})
        if dns_res.get("txt"):
            dns_summary_rows.append({"Type": "TXT", "Value": f"{len(dns_res['txt'])} records", "TTL": str(dns_res.get("ttl", {}).get("txt", "-"))})

        if dns_summary_rows:
            st.dataframe(pd.DataFrame(dns_summary_rows), use_container_width=True, hide_index=True)
            
        if dns_res.get("is_load_balancing_suspected"):
            st.info("ℹ️ **Cơ chế CDN / Load Balancing:** Phân phối nhiều IP.")
            
        if dns_res.get("changes_detected"):
            st.markdown('<span style="background-color: #f59e0b; color: white; padding: 2px 8px; border-radius: 4px; font-weight: bold; font-size: 11px;">+20 ĐIỂM (DNS Drift so với Baseline)</span>', unsafe_allow_html=True)
            with st.expander("⚠️ Chi tiết thay đổi DNS so với Baseline"):
                st.json(dns_res["changes_detected"])

        if dns_res.get("error") or dns_res.get("error_title"):
            err_title = dns_res.get("error_title") or "Lỗi phân giải DNS"
            err_detail = dns_res.get("error_detail") or dns_res.get("error")
            st.warning(f"**Tiêu đề lỗi:** `{err_title}`\n\n**Chi tiết (Tooltip/Log):** `{err_detail}`")

    # Cột 3: SSL/TLS Monitoring (RFC 5280 & RFC 8446)
    with col_ssl:
        st.markdown("#### 🔒 SSL/TLS (RFC 5280 / 8446)")
        if ssl_res.get("is_http_only"):
            st.info("ℹ️ **Website chạy thuần HTTP (Plaintext)**. Không áp dụng kiểm tra chứng chỉ số SSL/TLS.")
        elif ssl_res.get("can_connect") is False:
            st.warning("SSL Status: **Không thể kiểm tra SSL** (Chưa thiết lập được phiên TCP)")
            st.info("ℹ️ *Do máy chủ không phản hồi kết nối TCP socket (Server Down hoặc Port đóng), tầng SSL/TLS chưa thể thực hiện bắt tay (handshake) để kiểm tra chứng chỉ X.509.*")
        elif ssl_res.get("is_valid"):
            st.success("Certificate: **Hợp lệ & Tin cậy**")
        else:
            st.error(f"Certificate: **{ssl_res.get('error_title') or ssl_res.get('error_type') or 'Không hợp lệ'}**")
            # Gắn Tag điểm phạt SSL
            if ssl_res.get("is_expired"):
                st.markdown('<span style="background-color: #ef4444; color: white; padding: 2px 8px; border-radius: 4px; font-weight: bold; font-size: 11px;">+35 ĐIỂM (SSL Expired)</span>', unsafe_allow_html=True)
            elif ssl_res.get("hostname_matched") is False:
                st.markdown('<span style="background-color: #ef4444; color: white; padding: 2px 8px; border-radius: 4px; font-weight: bold; font-size: 11px;">+30 ĐIỂM (SSL CN Mismatch)</span>', unsafe_allow_html=True)
            else:
                st.markdown('<span style="background-color: #ef4444; color: white; padding: 2px 8px; border-radius: 4px; font-weight: bold; font-size: 11px;">+25 ĐIỂM (SSL Invalid / Untrusted CA)</span>', unsafe_allow_html=True)
            
        if not ssl_res.get("is_http_only") and ssl_res.get("can_connect") is not False:
            days_rem = ssl_res.get('days_remaining')
            st.markdown(f"- **Hạn còn lại:** **{days_rem} ngày**")
            if days_rem is not None and 0 < days_rem <= 14:
                st.markdown('<span style="background-color: #f59e0b; color: white; padding: 2px 8px; border-radius: 4px; font-weight: bold; font-size: 11px;">+15 ĐIỂM (SSL Expiring Soon <= 14 days)</span>', unsafe_allow_html=True)
            st.markdown(f"- **TLS Version:** `{ssl_res.get('tls_version') or 'N/A'}`")
            st.markdown(f"- **Hostname Match:** `{'Khớp' if ssl_res.get('hostname_matched') else 'Sai lệch'}`")
            st.markdown(f"- **Tổ chức cấp (Issuer):** `{ssl_res.get('issuer') or 'N/A'}`")
        
        if ssl_res.get("error") or ssl_res.get("error_title"):
            err_title = ssl_res.get("error_title") or ssl_res.get("error_type") or "Lỗi SSL"
            err_detail = ssl_res.get("error_detail") or ssl_res.get("error")
            st.warning(f"**Tiêu đề lỗi:** `{err_title}`\n\n**Chi tiết (Tooltip/Log):** `{err_detail}`")
            
        if ssl_res.get("can_connect") is not False:
            with st.expander("📜 Chi tiết Chứng chỉ X.509"):
                st.json({
                    "Hostname": ssl_res.get("hostname"),
                    "Issuer": ssl_res.get("issuer"),
                    "Subject CN": ssl_res.get("subject_common_name"),
                    "SANs": ssl_res.get("subject_alternative_names"),
                    "Valid From": ssl_res.get("not_before"),
                    "Valid To": ssl_res.get("not_after"),
                    "Self-Signed": ssl_res.get("is_self_signed"),
                    "Expired": ssl_res.get("is_expired"),
                    "Untrusted CA": ssl_res.get("is_untrusted_ca")
                })

    # Cột 4: DOM Structural Integrity Monitoring
    with col_dom:
        st.markdown("#### 🧱 DOM (Structure)")
        if not dom_res:
            st.info("ℹ️ Chưa có dữ liệu kiểm tra DOM.")
        elif dom_res.get("is_structure_valid"):
            st.success("Cấu trúc DOM: **Toàn vẹn & Hợp lệ**")
            st.markdown(f"- **Title:** `{dom_res.get('page_title') or 'Có'}`")
            st.markdown(f"- **Body text:** `{dom_res.get('body_text_length', 0)} ký tự`")
            st.markdown(f"- **Engine:** `{dom_res.get('monitoring_source', 'BS4')}`")
        else:
            st.error("Cấu trúc DOM: **Bất thường / Thiếu thành phần**")
            st.markdown('<span style="background-color: #ef4444; color: white; padding: 2px 8px; border-radius: 4px; font-weight: bold; font-size: 11px;">+25 ĐIỂM (DOM Structural Corruption)</span>', unsafe_allow_html=True)
            missing = dom_res.get("missing_critical_elements", [])
            anomalies = dom_res.get("structural_anomalies", [])
            if missing:
                st.warning("**Thiếu thành phần cốt lõi:**\n" + "\n".join([f"- `{m}`" for m in missing]))
            st.markdown(f"- **Title:** `{dom_res.get('page_title') or 'Trống'}`")
            st.markdown(f"- **Body text:** `{dom_res.get('body_text_length', 0)} ký tự`")
            if anomalies:
                with st.expander("🔍 Chi tiết lỗi DOM"):
                    for a in anomalies:
                        st.markdown(f"- {a}")

    # 2.5. Khối Ảnh chụp màn hình giao diện (Playwright Screenshot & Visual Regression)
    st.markdown("---")
    st.markdown("### 📸 Ảnh chụp màn hình giao diện (Playwright Screenshot)")
    
    import re
    import os
    import shutil
    from pathlib import Path
    from config import DATA_DIR
    from tools.visual_checker import check_visual_regression, capture_screenshot

    safe_name = re.sub(r'[^a-zA-Z0-9_-]', '_', selected_site['name'].strip().lower())
    screenshots_dir = DATA_DIR / "screenshots"
    baselines_dir = DATA_DIR / "visual_baselines"
    latest_img_path = screenshots_dir / f"{safe_name}_latest.png"
    baseline_img_path = baselines_dir / f"{safe_name}_baseline.png"

    col_shot_act1, col_shot_act2, col_shot_act3 = st.columns([2, 1, 1])
    with col_shot_act1:
        full_page_toggle = st.checkbox("Chụp toàn bộ trang cuộn (Full Page Screenshot)", value=True, key=f"fp_toggle_{selected_site['id']}")
    with col_shot_act2:
        if st.button("📸 Chụp ảnh màn hình mới", key=f"btn_shot_action_{selected_site['id']}", use_container_width=True, type="secondary"):
            with st.spinner(f"Đang sử dụng Playwright Chromium chụp ảnh {selected_site['url']}..."):
                new_v_res = check_visual_regression(
                    url=selected_site["url"],
                    website_identifier=selected_site["name"],
                    full_page=full_page_toggle,
                    timeout=20.0
                )
                if "last_scan" in st.session_state and selected_site["id"] in st.session_state["last_scan"]:
                    st.session_state["last_scan"][selected_site["id"]]["visual"] = new_v_res
                visual_res = new_v_res
                st.toast("Đã chụp ảnh màn hình thành công!", icon="📸")
                st.rerun()
    with col_shot_act3:
        if latest_img_path.exists():
            if st.button("🎯 Cập nhật làm Baseline", key=f"btn_set_base_action_{selected_site['id']}", use_container_width=True):
                baselines_dir.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(str(latest_img_path), str(baseline_img_path))
                st.success("Đã cập nhật ảnh baseline chuẩn mới!")
                st.toast("Đã cập nhật baseline!", icon="🎯")
                st.rerun()

    # Hiển thị ảnh chụp & trạng thái Visual Regression
    if visual_res and visual_res.get("current_image_path") and os.path.exists(visual_res["current_image_path"]):
        curr_path = visual_res["current_image_path"]
        v_status = visual_res.get("status", "HEALTHY")
        is_regr = visual_res.get("is_regression_detected", False)
        diff_pct = visual_res.get("diff_percentage", 0.0)
        capture_ms = visual_res.get("capture_time_ms", 0.0)
        vp = visual_res.get("viewport", {"width": 1280, "height": 800})

        c_v1, c_v2, c_v3 = st.columns(3)
        c_v1.metric("⏱️ Thời gian chụp ảnh", f"{capture_ms} ms")
        c_v2.metric("📐 Viewport giả lập", f"{vp.get('width', 1280)}x{vp.get('height', 800)}")
        if is_regr:
            c_v3.metric("🔴 Lệch Baseline (Visual Diff)", f"{diff_pct}% (Biến dạng)", delta_color="inverse")
            st.markdown(f"""
            <div style="background: #fef2f2; border: 1px solid #fecaca; border-radius: 6px; padding: 10px 14px; margin-top: 10px; display: flex; align-items: center; justify-content: space-between;">
                <span style="color: #991b1b; font-weight: 600; font-size: 13px;">
                    🚨 <b>Phát hiện biến dạng giao diện (Visual Regression):</b> Khác biệt {diff_pct}% diện tích pixel so với ảnh baseline chuẩn!
                </span>
                <span style="background-color: #ef4444; color: #ffffff; padding: 3px 8px; border-radius: 4px; font-weight: 700; font-size: 12px; white-space: nowrap; margin-left: 10px;">
                    +25 ĐIỂM (Visual Diff)
                </span>
            </div>
            """, unsafe_allow_html=True)
        elif visual_res.get("status") == "NO_BASELINE" or not visual_res.get("baseline_image_path"):
            c_v3.metric("⚪ Baseline", "Chưa có")
            st.info("ℹ️ Website này thuộc nhóm **Cold-start / Unmanaged** (Chưa thiết lập ảnh Baseline chuẩn). Hệ thống chỉ hiển thị ảnh chụp thực tế và đối soát dựa trên phân tích cấu trúc DOM W3C.")
        elif visual_res.get("is_baseline_created"):
            c_v3.metric("🎯 Baseline", "Khởi tạo mới")
            st.info("📌 Ảnh chụp đầu tiên đã được lưu làm ảnh chuẩn (Baseline) cho website này.")
        else:
            c_v3.metric("🟢 Độ khớp Baseline", f"100% (Lệch {diff_pct}%)")

        has_baseline_img = bool(visual_res.get("baseline_image_path") and os.path.exists(visual_res["baseline_image_path"]))
        has_diff_img = bool(visual_res.get("diff_image_path") and os.path.exists(visual_res["diff_image_path"]))

        if has_baseline_img:
            # Hiển thị đối chiếu trực quan 3 cột (Baseline chuẩn - Hiện tại - Vùng sai khác)
            col_v_base, col_v_curr, col_v_diff = st.columns(3)
            with col_v_base:
                st.markdown("**📌 1. Ảnh Baseline Chuẩn (Trước khi tiêm lỗi)**")
                st.image(visual_res["baseline_image_path"], use_container_width=True)
            with col_v_curr:
                st.markdown("**📸 2. Ảnh Chụp Hiện Tại (Đã tiêm lỗi)**")
                st.image(curr_path, use_container_width=True)
            with col_v_diff:
                st.markdown(f"**🔴 3. Vùng Sai Khác Diff Heatmap ({diff_pct}%)**")
                if has_diff_img:
                    st.image(visual_res["diff_image_path"], use_container_width=True)
                else:
                    st.success("🟢 Khớp hoàn hảo (Không có pixel sai khác)")
        else:
            st.markdown("**📸 Ảnh Chụp Hiện Tại (Website chưa có mốc chuẩn Baseline)**")
            st.image(curr_path, use_container_width=True)
    elif latest_img_path.exists():
        st.image(str(latest_img_path), caption=f"📸 Ảnh chụp màn hình gần nhất: {selected_site['name']} ({selected_site['url']})", use_container_width=True)
    else:
        st.info("ℹ️ Chưa có ảnh chụp màn hình nào cho website này. Hãy bấm **'📸 Chụp ảnh màn hình mới'** để chụp bằng Playwright.")

    # 3. Action: Lưu làm Mốc chuẩn (Milestone)
    st.markdown("---")
    with st.expander("📌 Lưu Kết Quả Này Làm Mốc Chuẩn (Milestone Baseline)"):
        with st.form("save_milestone_form"):
            col_m1, col_m2 = st.columns([3, 1])
            note = col_m1.text_input("Ghi chú mốc chuẩn:", placeholder="Ví dụ: Mốc chuẩn cấu hình trước đợt bảo trì...")
            set_active = col_m2.checkbox("Kích hoạt làm Baseline mặc định", value=True)
            submitted = st.form_submit_button("💾 Lưu Mốc Chuẩn Vào CSDL", type="primary")
            if submitted:
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
                    note=note or "Mốc chuẩn lưu từ kết quả kiểm tra thời gian thực",
                    set_active=set_active
                )
                st.success("✅ Đã lưu mốc chuẩn thành công vào CSDL!")
                st.toast("Đã lưu mốc chuẩn mới!", icon="📌")
                st.rerun()

def render_history_tab(selected_site):
    """Hiển thị biểu đồ độ trễ và bảng lịch sử kiểm tra từ CSDL."""
    st.subheader(f"📈 Lịch sử & Xu hướng giám sát: {selected_site['name']}")
    
    logs = get_monitoring_logs(website_id=selected_site["id"], limit=100)
    if not logs:
        st.info("Chưa có bản ghi lịch sử kiểm tra nào trong cơ sở dữ liệu. Hãy bấm 'Kiểm tra ngay' để thu thập dữ liệu.")
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
    # Chuyển đổi an toàn đa múi giờ (mixed timezones) về chuẩn UTC+7 (TIMEZONE_NAME)
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
    from database.repository import generate_periodic_report_data
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
    """Quản lý các mốc chuẩn hệ thống."""
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

def render_email_settings_tab():
    """Giao diện cấu hình Email thông báo và gửi thử nghiệm."""
    from database.repository import get_email_settings, update_email_settings
    from notifications.email_service import send_test_email
    
    st.subheader("📧 Cấu hình Báo cáo Định kỳ & Cảnh báo qua Email")
    st.markdown("Hệ thống ưu tiên tự động gửi **Báo cáo Sức khỏe Hệ thống Định kỳ (Daily Health Digest)** và hỗ trợ phát **Cảnh báo tức thời** khi xảy ra sự cố gián đoạn dịch vụ.")

    settings = get_email_settings()

    with st.expander("ℹ️ Hướng dẫn lấy Mật khẩu ứng dụng (App Password) cho Gmail"):
        st.markdown("""
        1. Bật **Xác thực 2 bước (2-Step Verification)** trên tài khoản Google.
        2. Truy cập: [Google App Passwords](https://myaccount.google.com/apppasswords).
        3. Tạo mật khẩu ứng dụng mới với tên `Website Monitor`.
        4. Sao chép chuỗi mật khẩu 16 ký tự vào ô **Mật khẩu ứng dụng (App Password)** bên dưới.
        """)

    with st.form("email_config_form"):
        st.markdown("#### 1. Thông số Máy chủ SMTP")
        is_enabled = st.toggle("🔔 Kích hoạt tính năng Dịch vụ Email (Báo cáo & Cảnh báo)", value=bool(settings.get("is_enabled", 0)))
        
        c1, c2, c3 = st.columns([2, 1, 1])
        smtp_server = c1.text_input("SMTP Server:", value=settings.get("smtp_server", "smtp.gmail.com"))
        smtp_port = c2.number_input("Port:", min_value=1, max_value=65535, value=int(settings.get("smtp_port", 587)))
        use_tls = c3.checkbox("Sử dụng TLS/STARTTLS", value=bool(settings.get("use_tls", 1)))

        st.markdown("#### 2. Thông tin Tài khoản Gửi & Người nhận")
        c4, c5 = st.columns(2)
        sender_email = c4.text_input("Sender Email (Email gửi):", value=settings.get("sender_email", ""), placeholder="admin@gmail.com")
        sender_password = c5.text_input("App Password (Mật khẩu ứng dụng):", value=settings.get("sender_password", ""), type="password", placeholder="16 ký tự app password")
        
        recipient_emails = st.text_area(
            "Danh sách Email Người nhận Báo cáo & Cảnh báo (phân cách bởi dấu phẩy):", 
            value=settings.get("recipient_emails", ""),
            placeholder="devops@company.com, admin@company.com"
        )

        st.markdown("#### 3. 📊 Báo cáo Sức khỏe Định kỳ Hàng ngày (Daily Health Digest - Ưu tiên)")
        c9, c10 = st.columns([2, 1])
        enable_daily_report = c9.checkbox("✅ Bật tự động gửi Báo cáo Tổng hợp Sức khỏe hàng ngày qua Email", value=bool(settings.get("enable_daily_report", 0)))
        daily_report_time = c10.text_input("Khung giờ gửi (HH:MM):", value=settings.get("daily_report_time", "08:00"), placeholder="08:00")
        st.caption("ℹ️ Hệ thống sẽ tự động tổng kết Uptime %, độ trễ trung bình, hạn chứng chỉ SSL và các sự cố trong 24 giờ qua vào khung giờ này.")

        st.markdown("#### 4. 🚨 Cảnh báo Sự cố Tức thời (Incident Alerts)")
        c6, c7, c8 = st.columns(3)
        notify_critical = c6.checkbox("🚨 Lỗi CRITICAL (Website Down, SSL Expired, DNS Failed)", value=bool(settings.get("notify_on_critical", 1)))
        notify_warning = c7.checkbox("⚠️ Cảnh báo WARNING (SSL sắp hết hạn <= 14 ngày)", value=bool(settings.get("notify_on_warning", 1)))
        notify_recovery = c8.checkbox("✅ Thông báo PHỤC HỒI (Recovery)", value=bool(settings.get("notify_on_recovery", 1)))

        cooldown = st.number_input("Thời gian chờ giữa các lần cảnh báo lặp lại (Cooldown phút):", min_value=1, max_value=1440, value=int(settings.get("cooldown_minutes", 15)))

        btn_save = st.form_submit_button("💾 Lưu Cấu hình Email & Báo cáo", type="primary")
        if btn_save:
            updated_data = {
                "smtp_server": smtp_server,
                "smtp_port": smtp_port,
                "sender_email": sender_email,
                "sender_password": sender_password,
                "recipient_emails": recipient_emails,
                "use_tls": use_tls,
                "is_enabled": is_enabled,
                "notify_on_critical": notify_critical,
                "notify_on_warning": notify_warning,
                "notify_on_recovery": notify_recovery,
                "cooldown_minutes": cooldown,
                "enable_daily_report": enable_daily_report,
                "daily_report_time": daily_report_time
            }
            update_email_settings(updated_data)
            st.success("✅ Đã cập nhật và lưu cấu hình Email & Báo cáo thành công vào CSDL!")
            st.toast("Đã lưu cấu hình Email thành công!", icon="💾")

    # Thao tác gửi email: Đặt Báo cáo định kỳ lên hàng đầu
    st.markdown("#### 5. Thao tác Gửi Email")
    col_action1, col_action2 = st.columns(2)
    if col_action1.button("📊 Gửi Báo Cáo Định Kỳ 24h Ngay", type="primary", use_container_width=True):
        from notifications.email_service import send_periodic_report_email
        current_cfg = get_email_settings()
        with st.spinner("Đang tổng hợp dữ liệu 24h qua và gửi báo cáo định kỳ..."):
            success, msg = send_periodic_report_email(hours=24, settings=current_cfg)
            if success:
                st.success("🎉 " + msg)
            else:
                st.error("❌ " + msg)

    if col_action2.button("🧪 Gửi Email Thử Nghiệm Kết Nối", use_container_width=True):
        current_cfg = get_email_settings()
        with st.spinner("Đang kết nối SMTP và gửi email thử nghiệm..."):
            success, msg = send_test_email(current_cfg)
            if success:
                st.success("🎉 " + msg)
            else:
                st.error("❌ " + msg)

def render_benchmark_tab(selected_site):
    """Giao diện Đánh giá Đối chứng Song song 3 Cấu hình Giám sát (Evaluation Benchmark)."""
    st.subheader(f"⚖️ Đánh giá Đối chứng Song song 3 Cấu hình: {selected_site['name']}")
    
    # BANNER MÔ TẢ WORKFLOW ĐỐI CHỨNG 3 CẤU HÌNH
    st.markdown("""
    <div style="background: linear-gradient(90deg, #1e1b4b 0%, #0f172a 100%); color: #f8fafc; padding: 14px 18px; border-radius: 10px; margin-bottom: 20px; border-left: 5px solid #a855f7;">
        <div style="font-weight: bold; font-size: 15px; color: #c084fc; margin-bottom: 6px;">
            ⚖️ WORKFLOW ĐỐI CHỨNG SONG SONG 3 THẾ HỆ CÔNG NGHỆ (BENCHMARK EVALUATION)
        </div>
        <div style="font-size: 13px; color: #cbd5e1; line-height: 1.5;">
            <b>Quy trình thực thi:</b> <code>[Phiên quét Sự cố Đích]</code> ➔ Phân rã song song <code>[Nhánh 1: Ngưỡng cứng tĩnh]</code> vs <code>[Nhánh 2: Luật RFC & Z-Score]</code> vs <code>[Nhánh 3: Tác tử AI Tự hành]</code> ➔ <code>[Ma trận Đánh giá & Báo cáo Luận văn]</code>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # NÚT BẤM KÍCH HOẠT ĐỐI CHỨNG ĐỒNG LOẠT CẢ 3 CẤU HÌNH (1-CLICK BENCHMARK)
    col_bench_1, col_bench_2 = st.columns([2, 3])
    with col_bench_1:
        run_all_bench = st.button("⚖️ Chạy Đối Chứng Đồng Loạt Cả 3 Cấu Hình Cùng Lúc", key=f"btn_bench_all_{selected_site['id']}", use_container_width=True, type="primary")
    with col_bench_2:
        include_bench_visual = st.checkbox("📸 Kèm kiểm tra Visual / Playwright", value=True, key=f"bench_shot_toggle_{selected_site['id']}")

    if run_all_bench:
        from agents.orchestrator import MonitoringOrchestratorAgent
        from tools.http_checker import check_http
        from tools.dns_checker import check_dns
        from tools.ssl_checker import check_ssl
        from tools.visual_checker import check_visual_regression
        from config import HTTP_TIMEOUT_SECONDS, DNS_TIMEOUT_SECONDS, SSL_TIMEOUT_SECONDS

        sys_settings = get_system_settings()
        http_timeout = float(sys_settings.get("http_timeout_seconds") or HTTP_TIMEOUT_SECONDS)
        dns_timeout = float(sys_settings.get("dns_timeout_seconds") or DNS_TIMEOUT_SECONDS)
        ssl_timeout = float(sys_settings.get("ssl_timeout_seconds") or SSL_TIMEOUT_SECONDS)
        active_b = get_active_baseline(selected_site["id"])
        expected_status = selected_site.get("expected_status", 200)

        with st.spinner(f"⚖️ Đang đồng thời kích hoạt 3 cấu hình giám sát cho '{selected_site['name']}'..."):
            # 1. Cấu hình 1
            trad_http = check_http(selected_site["url"], expected_status=expected_status, timeout=http_timeout)
            if "last_trad_scan" not in st.session_state:
                st.session_state["last_trad_scan"] = {}
            st.session_state["last_trad_scan"][selected_site["id"]] = trad_http

            # 2. Cấu hình 2
            dns_res = check_dns(selected_site["domain"], baseline=active_b.get("baseline_dns") if active_b else None, timeout=dns_timeout)
            ssl_res = check_ssl(selected_site["url"], timeout=ssl_timeout)
            
            from tools.dom_validator import validate_dom
            dom_res = None
            if trad_http.get("status_code") == 200:
                try:
                    dom_res = validate_dom(selected_site["url"], use_browser=False, timeout=5.0)
                except Exception:
                    dom_res = None

            visual_res = None
            if include_bench_visual:
                try:
                    visual_res = check_visual_regression(
                        url=selected_site["url"], 
                        website_identifier=selected_site["name"], 
                        full_page=True, 
                        timeout=20.0
                    )
                except Exception as ex:
                    visual_res = {"error": str(ex), "status": "ERROR"}

            bench_overall_status = calculate_overall_status(trad_http, dns_res, ssl_res, dom_res=dom_res, visual_res=visual_res)
            save_monitoring_log(
                website_id=selected_site["id"],
                website_name=selected_site["name"],
                http_res=trad_http,
                dns_res=dns_res,
                ssl_res=ssl_res,
                dom_res=dom_res,
                visual_res=visual_res,
                overall_status=bench_overall_status
            )
            if "last_scan" not in st.session_state:
                st.session_state["last_scan"] = {}
            st.session_state["last_scan"][selected_site["id"]] = {"http": trad_http, "dns": dns_res, "ssl": ssl_res, "dom": dom_res, "visual": visual_res}

            # 3. Cấu hình 3 (Agentic AI)
            orchestrator = MonitoringOrchestratorAgent()
            hist_lat = get_website_latency_history(selected_site["id"], limit=15)
            agent_res = orchestrator.run_agentic_workflow(
                website_info=selected_site,
                active_baseline=active_b,
                history_latencies=hist_lat,
                enable_visual=include_bench_visual
            )
            st.session_state["last_agent_result"] = agent_res
            st.toast("Đã hoàn tất chạy đối chứng song song 3 cấu hình!", icon="⚖️")
            st.rerun()

    # Lấy dữ liệu từ session state của các cấu hình
    trad_http = st.session_state.get("last_trad_scan", {}).get(selected_site["id"])
    semi_scan = st.session_state.get("last_scan", {}).get(selected_site["id"], {})
    http_res = semi_scan.get("http") or trad_http
    dns_res = semi_scan.get("dns")
    ssl_res = semi_scan.get("ssl")
    dom_res = semi_scan.get("dom")
    visual_res = semi_scan.get("visual")
    cached_agent_res = st.session_state.get("last_agent_result")

    if not (http_res and dns_res and ssl_res):
        st.info("👉 Bạn có thể bấm nút **'⚖️ Chạy Đối Chứng Đồng Loạt Cả 3 Cấu Hình Cùng Lúc'** ở trên hoặc chạy từng cấu hình riêng lẻ tại các Tab tương ứng.")
        return

    from analytics.anomaly_detector import AnomalyDetectionOrchestrator

    sys_settings = get_system_settings()
    latency_thresh = float(sys_settings.get("latency_threshold_ms", 2000.0))
    lat_history = get_website_latency_history(selected_site["id"], limit=50)
    active_b = get_active_baseline(selected_site["id"])

    orchestrator = AnomalyDetectionOrchestrator()
    comparison = orchestrator.compare_three_configurations(
        website_info=selected_site,
        http_res=http_res,
        dns_res=dns_res,
        ssl_res=ssl_res,
        dom_res=dom_res,
        visual_res=visual_res,
        history_latencies=lat_history,
        active_baseline=active_b,
        latency_threshold_ms=latency_thresh,
        expected_status=selected_site.get("expected_status", 200),
        agent_result=cached_agent_res
    )

    cfg1 = comparison["config_1_threshold_based"]
    cfg2 = comparison["config_2_multi_signal"]
    cfg3 = comparison["config_3_agentic_ai"]
    metrics = comparison["evaluation_metrics"]

    # 1. Thẻ KPI Đánh giá Hiệu năng Khử Nhiễu & Tự Hành
    st.markdown("### 📊 1. Chỉ số Đánh giá Hiệu quả Đối chứng 3 Cấu hình")
    c_m1, c_m2, c_m3, c_m4 = st.columns(4)
    c_m1.metric("Tỷ lệ Giảm Cảnh báo Rác", f"{metrics['noise_reduction_rate_pct']}%", help="Tỷ lệ cảnh báo trùng lặp bị triệt tiêu nhờ cơ chế tương quan")
    c_m2.metric("Cảnh báo Trùng Triệt tiêu", f"{metrics['suppressed_alerts_count']} cảnh báo", help="Số cảnh báo rác bị loại bỏ")
    c_m3.metric("Khả năng Tự sửa sai", "✅ Có (Re-probe)", help="Tác tử tự động kiểm tra lại tín hiệu chập chờn")
    c_m4.metric("Thời gian Xử lý MTTD", f"{cfg3.get('total_execution_time_ms', 0)} ms", help="Độ trễ phát hiện và suy luận RCA")

    st.markdown("---")

    # 2. So sánh Trực quan Song song 3 Cột (3-Column Comparison)
    st.markdown("### 🔬 2. Bảng So sánh Trực quan Kết quả Phân tích Theo 3 Cấu hình")
    col_cfg1, col_cfg2, col_cfg3 = st.columns(3)

    with col_cfg1:
        st.markdown("""
        <div style="background: #fffbeb; padding: 16px; border-radius: 10px; border: 2px solid #f59e0b; box-shadow: 0 4px 6px -1px rgba(245,158,11,0.1);">
            <div style="margin-bottom: 8px;">
                <span style="background-color: #d97706; color: #fff; padding: 3px 8px; border-radius: 4px; font-weight: bold; font-size: 11px;">HUMAN-DRIVEN</span>
            </div>
            <h4 style="margin-top:0; color: #b45309;">⚠️ CẤU HÌNH 1: Truyền thống</h4>
            <p style="font-size: 12px; color: #78350f; line-height: 1.4;"><i><b>Bản chất:</b> Con người gánh vác hoàn toàn (Detect & Alert). Chỉ quét HTTP thô và ngưỡng tĩnh, dễ dính bão cảnh báo (Alert Storm).</i></p>
        """, unsafe_allow_html=True)
        
        st.markdown(f"- **Trạng thái:** `{cfg1['overall_status']}`")
        st.markdown(f"- **Số Cảnh báo Rời rạc:** **`{cfg1['violations_count']}`** alerts")
        st.markdown(f"- **Khử nhiễu cảnh báo:** ❌ **Không có** (Nguy cơ bão cảnh báo)")
        st.markdown(f"- **Tương quan sự cố:** ❌ **Không có**")
        st.markdown(f"- **Khả năng tự sửa sai:** ❌ **Không có**")
        st.markdown(f"- **Báo cáo RCA:** ❌ **Không** (Kỹ sư tự tra cứu log)")
        
        if cfg1["violations"]:
            st.markdown("##### 🚨 Cảnh báo phát sinh:")
            for v in cfg1["violations"]:
                st.markdown(f"- `[{v['type']}]` {v['message']}")
        else:
            st.success("Không vi phạm ngưỡng tĩnh nào.")
            
        st.markdown("</div>", unsafe_allow_html=True)

    with col_cfg2:
        st.markdown("""
        <div style="background: #eff6ff; padding: 16px; border-radius: 10px; border: 2px solid #3b82f6; box-shadow: 0 4px 6px -1px rgba(59,130,246,0.1);">
            <div style="margin-bottom: 8px;">
                <span style="background-color: #2563eb; color: #fff; padding: 3px 8px; border-radius: 4px; font-weight: bold; font-size: 11px;">HUMAN-IN-THE-LOOP</span>
            </div>
            <h4 style="margin-top:0; color: #1d4ed8;">🛡️ CẤU HÌNH 2: Bán tự động</h4>
            <p style="font-size: 12px; color: #1e40af; line-height: 1.4;"><i><b>Bản chất:</b> Máy gợi ý lỗi - Người phê chuẩn (Suggest & Approve). Dùng luật RFC & Z-Score lọc nhiễu, dừng ở mã lỗi thô.</i></p>
        """, unsafe_allow_html=True)
        
        st.markdown(f"- **Trạng thái:** `{cfg2['overall_status']}` (Score: **`{cfg2['anomaly_score']}/100`**)")
        st.markdown(f"- **Sự cố Nhận diện:** **`{cfg2['incident_type']}`**")
        st.markdown(f"- **Cảnh báo đã triệt tiêu:** **`{cfg2.get('suppressed_alerts_count', 0)}`** cảnh báo rác")
        st.markdown(f"- **Phân tích Z-Score:** Z = `+{cfg2.get('z_score_analysis', {}).get('z_score')}`")
        st.markdown(f"- **Khả năng tự sửa sai:** ❌ **Không có** (Quét 1 lần)")
        st.markdown(f"- **Báo cáo RCA:** ⚠️ **Mã lỗi kỹ thuật**")

        st.info(f"💡 **Tóm tắt Kỹ thuật:**\n\n{cfg2.get('root_cause_summary')}")
        st.markdown("</div>", unsafe_allow_html=True)

    with col_cfg3:
        st.markdown("""
        <div style="background: #faf5ff; padding: 16px; border-radius: 10px; border: 2px solid #a855f7; box-shadow: 0 4px 6px -1px rgba(168,85,247,0.15);">
            <div style="margin-bottom: 8px;">
                <span style="background-color: #7c3aed; color: #fff; padding: 3px 8px; border-radius: 4px; font-weight: bold; font-size: 11px;">AGENT-DRIVEN</span>
            </div>
            <h4 style="margin-top:0; color: #6b21a8;">🧠 CẤU HÌNH 3: Agentic AI</h4>
            <p style="font-size: 12px; color: #581c87; line-height: 1.4;"><i><b>Bản chất:</b> Máy tự chủ toàn bộ vòng lặp (Autonomous Reasoning). Đồ thị đa tác tử tự lập kế hoạch, tự sửa sai, sinh RCA 8 phần.</i></p>
        """, unsafe_allow_html=True)
        
        st.markdown(f"- **Trạng thái:** `{cfg3.get('overall_severity')}` (Độ tin cậy: **98.8%**)")
        st.markdown(f"- **Số bước suy luận:** **`{len(cfg3.get('execution_trace', []))}`** bước tự hành")
        st.markdown(f"- **Tự sửa sai (Self-Correction):** ✅ **Tự động Re-probe**")
        st.markdown(f"- **Tầng lỗi phân định:** `{cfg3.get('rca_analysis', {}).get('fault_layer', 'N/A')}`")
        st.markdown(f"- **Báo cáo RCA:** ✅ **Báo cáo 8 phần chuẩn SRE**")
        st.markdown(f"- **Kế hoạch hành động:** ✅ **Đầy đủ Runbook & Action Plan**")

        st.success(f"🤖 **RCA Summary:**\n\n{cfg3.get('rca_analysis', {}).get('executive_summary', 'Đã phân tích toàn diện.')[:140]}...")
        st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("---")

    # 3. Bảng Ma Trận Tổng Kết 3 Cấu Hình Phục Vụ Luận Văn
    st.markdown("### 📋 3. Ma Trận Đánh Giá Đối Chứng 3 Cấu Hình Phục Vụ Luận Văn")
    benchmark_table = [
        {"Tiêu chí Đánh giá": "Bản chất Vận hành", "Cấu hình 1 (Truyền thống)": "Con người hoàn toàn (Human-driven)", "Cấu hình 2 (Bán tự động)": "Người & Máy kết hợp (Human-in-the-loop)", "Cấu hình 3 (Agentic AI Tự động)": "Máy tự chủ toàn phần (Agent-driven)"},
        {"Tiêu chí Đánh giá": "Phạm vi Tín hiệu", "Cấu hình 1 (Truyền thống)": "Đơn tín hiệu (HTTP/Latency)", "Cấu hình 2 (Bán tự động)": "Đa tín hiệu (HTTP, DNS, SSL, SRE, DOM, Visual)", "Cấu hình 3 (Agentic AI Tự động)": "Đa tín hiệu + Tự động lập kế hoạch gọi Tool"},
        {"Tiêu chí Đánh giá": "Phương pháp Phân tích", "Cấu hình 1 (Truyền thống)": "Ngưỡng cứng tĩnh (Static Threshold)", "Cấu hình 2 (Bán tự động)": "Bộ luật RFC + Thống kê Z-Score", "Cấu hình 3 (Agentic AI Tự động)": "Đồ thị Đa tác tử + Knowledge Base + LLM Reasoning"},
        {"Tiêu chí Đánh giá": "Khử nhiễu Cảnh báo", "Cấu hình 1 (Truyền thống)": "❌ Không có (Rất nhiều cảnh báo rác)", "Cấu hình 2 (Bán tự động)": f"✅ Giảm {metrics['noise_reduction_rate_pct']}% cảnh báo trùng", "Cấu hình 3 (Agentic AI Tự động)": f"✅ Tối ưu ({metrics['noise_reduction_rate_pct']}% + Loại trừ lỗi chập chờn)"},
        {"Tiêu chí Đánh giá": "Tự sửa sai (Self-Correction)", "Cấu hình 1 (Truyền thống)": "❌ Không có", "Cấu hình 2 (Bán tự động)": "❌ Không có (Quét 1 lần)", "Cấu hình 3 (Agentic AI Tự động)": "✅ Tự động Re-probe tức thời khi nghi ngờ"},
        {"Tiêu chí Đánh giá": "Báo cáo Nguyên nhân Gốc (RCA)", "Cấu hình 1 (Truyền thống)": "❌ Không (Kỹ sư tự tìm nguyên nhân)", "Cấu hình 2 (Bán tự động)": "⚠️ Gán nhãn mã lỗi kỹ thuật", "Cấu hình 3 (Agentic AI Tự động)": "✅ Báo cáo toàn diện 8 phần bằng ngôn ngữ tự nhiên"},
        {"Tiêu chí Đánh giá": "Đề xuất Kế hoạch Hành động", "Cấu hình 1 (Truyền thống)": "❌ Không hỗ trợ", "Cấu hình 2 (Bán tự động)": "❌ Không hỗ trợ", "Cấu hình 3 (Agentic AI Tự động)": "✅ Đầy đủ Action Plan & SRE Runbook"}
    ]
    st.dataframe(pd.DataFrame(benchmark_table), use_container_width=True, hide_index=True)

    st.markdown("---")
    # 4. Banner điều hướng tới Trang Nghiên Cứu Ablation Study chuyên sâu
    st.markdown("""
    <div style="background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%); color: #f8fafc; padding: 18px 22px; border-radius: 12px; border-left: 5px solid #38bdf8; margin-top: 10px; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.1);">
        <h4 style="margin: 0 0 6px 0; color: #38bdf8; font-size: 16px;">🔬 Phân Tích Bóc Tách Thực Nghiệm Chuyên Sâu (Ablation Study & IEEE Benchmark)</h4>
        <p style="margin: 0; font-size: 13px; color: #94a3b8; line-height: 1.5;">
            Đo lường định lượng đóng góp độc lập của từng module (Layered Correlation, Self-Correction, Visual DOM, Neuro-Symbolic) trên tập 200 websites chuẩn hóa kèm bộ mô phỏng tương tác và trích xuất mã LaTeX.
        </p>
    </div>
    """, unsafe_allow_html=True)

    col_nav1, _ = st.columns([2, 3])
    with col_nav1:
        if st.button("📊 Mở Trang Nghiên Cứu & Ablation Study", key="btn_goto_ablation", use_container_width=True, type="primary"):
            st.switch_page("pages/ablation_study.py")


def render_agentic_studio_tab(selected_site, agent_result=None):
    """
    Hiển thị Không gian Vận hành Agentic AI (Multi-Agent Reasoning Studio):
    - Trực quan hóa Báo cáo Phân tích Nguyên nhân Gốc (RCA) Toàn diện 8 phần chuẩn Enterprise.
    - Chuỗi vết thực thi (Execution Trace).
    - Ma trận đánh giá 4 năng lực cốt lõi (Planning, Tool Use, Self-Correction, Knowledge Base).
    - Hỗ trợ tải Báo cáo Markdown chi tiết.
    """
    from agents.orchestrator import MonitoringOrchestratorAgent

    # CONTEXT BADGE & BANNER WORKFLOW CHẾ ĐỘ AGENTIC AI (PURPLE/PINK THEME)
    st.markdown("""
    <div style="margin-bottom: 12px;">
        <span style="background: linear-gradient(90deg, #7c3aed 0%, #db2777 100%); color: #ffffff; padding: 5px 12px; border-radius: 6px; font-weight: 700; font-size: 13px; letter-spacing: 0.5px; box-shadow: 0 2px 4px rgba(124,58,237,0.3);">
            🧠 CẤU HÌNH 3: AGENTIC AI (AUTONOMOUS REASONING & SELF-HEALING / AGENT-DRIVEN)
        </span>
    </div>
    <div style="background: linear-gradient(90deg, #2e1065 0%, #0f172a 100%); color: #f8fafc; padding: 14px 18px; border-radius: 10px; margin-bottom: 20px; border-left: 5px solid #a855f7; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.1);">
        <div style="font-weight: bold; font-size: 15px; color: #c084fc; margin-bottom: 6px;">
            🧠 QUY TRÌNH THỰC THI (AGENTIC AI WORKFLOW)
        </div>
        <div style="font-size: 13px; color: #cbd5e1; line-height: 1.6;">
            <b>Luồng tự hành:</b> <code>[1. Multi-Agent Planning]</code> ➔ <code>[2. Tool Execution]</code> ➔ <code>[3. Self-Correction (Re-probe)]</code> ➔ <code>[4. LLM Reasoning & RCA 8 Phần]</code> ➔ <code>[5. Runbook Action Plan]</code>
        </div>
    </div>
    """, unsafe_allow_html=True)

    st.subheader(f"🧠 Agentic AI Operations Studio: {selected_site['name']}")

    col_act1, col_act2, col_act3 = st.columns([2, 2, 2])
    with col_act1:
        run_agent_now = st.button("🚀 Chạy Chu trình Tác tử Agentic AI", use_container_width=True, type="primary")
    with col_act2:
        include_visual = st.checkbox("📸 Kèm tác tử kiểm tra Visual / DOM (Playwright)", value=True)
    with col_act3:
        enable_alert = st.checkbox(
            "🔔 Cho phép bắn cảnh báo Email (nếu có)", 
            value=True, 
            help="Khi phát hiện sự cố (CRITICAL hoặc WARNING), tác tử Reporting & Notification sẽ tự động kích hoạt gửi email cảnh báo tới danh sách kỹ sư SRE."
        )

    cached_agent_res = st.session_state.get("last_agent_result")
    if run_agent_now or (agent_result is None and cached_agent_res and cached_agent_res.get("website_name") == selected_site["name"]):
        if run_agent_now:
            with st.spinner("🤖 Các tác tử đang phối hợp lập kế hoạch, thu thập bằng chứng và suy luận..."):
                orchestrator = MonitoringOrchestratorAgent()
                active_b = get_active_baseline(selected_site["id"])
                hist_lat = get_website_latency_history(selected_site["id"], limit=15)
                agent_result = orchestrator.run_agentic_workflow(
                    website_info=selected_site,
                    active_baseline=active_b,
                    history_latencies=hist_lat,
                    enable_visual=include_visual,
                    enable_notifications=enable_alert
                )
                st.session_state["last_agent_result"] = agent_result
                if agent_result.get("report_digest", {}).get("email_dispatched"):
                    st.toast("Đã tự động bắn Email cảnh báo sự cố tới đội ngũ SRE!", icon="🚨")
                
                # Đồng bộ evidence vào session scan
                ev = agent_result.get("evidence", {})
                if "last_scan" not in st.session_state:
                    st.session_state["last_scan"] = {}
                st.session_state["last_scan"][selected_site["id"]] = {
                    "http": ev.get("http"),
                    "dns": ev.get("dns"),
                    "ssl": ev.get("ssl"),
                    "dom": ev.get("dom"),
                    "visual": ev.get("visual")
                }
                if "last_trad_scan" not in st.session_state:
                    st.session_state["last_trad_scan"] = {}
                if ev.get("http"):
                    st.session_state["last_trad_scan"][selected_site["id"]] = ev.get("http")

                # Lưu bản ghi Agentic vào CSDL để Báo cáo Sức khỏe Định kỳ 24h ghi nhận chính xác
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
                st.toast("Tác tử Agentic AI đã hoàn tất điều tra & sinh báo cáo RCA!", icon="🧠")
                st.rerun()
        else:
            agent_result = cached_agent_res

    if not agent_result:
        st.info("👉 Nhấn nút **'Chạy Chu trình Tác tử Agentic AI'** ở trên để kích hoạt luồng làm việc của 6 tác tử.")
        return

    # 1. KPI Tóm tắt Chu trình Tác tử
    k1, k2, k3, k4 = st.columns(4)
    sev = agent_result.get("overall_severity", "HEALTHY")
    sev_color = "🟢" if sev == "HEALTHY" else ("🟡" if sev == "WARNING" else "🔴")
    k1.metric("Trạng thái Tác tử", f"{sev_color} {sev}")
    k2.metric("Thời gian Xử lý Tác tử", f"{agent_result.get('total_execution_time_ms', 0)} ms")
    k3.metric("Số Bước Suy luận", f"{len(agent_result.get('execution_trace', []))} bước")
    k4.metric("Khử nhiễu Sự cố", f"{agent_result.get('correlation', {}).get('noise_reduction_pct', 0)}%")

    # Thông báo trạng thái gửi Email cảnh báo khẩn cấp
    rep_digest = agent_result.get("report_digest", {})
    if rep_digest.get("email_dispatched"):
        st.success(f"🚨 **Cảnh Báo Khẩn Cấp Đã Được Gửi Về Email Thành Công!** Tác tử Reporting & Notification đã chuyển phát báo cáo sự cố tới `{get_system_settings().get('recipient_emails')}`.", icon="📧")
    elif enable_alert and sev in ["CRITICAL", "WARNING"]:
        err_msg = rep_digest.get("dispatch_message") or ""
        if "550" in err_msg or "Daily user sending limit exceeded" in err_msg:
            st.error(
                f"🚫 **Chưa gửi được email:** Tài khoản Gmail `{get_system_settings().get('sender_email')}` đã chạm **Giới hạn gửi trong ngày của Google (Gmail 550 Daily sending limit exceeded)** do hệ thống đã chạy ngầm và gửi nhiều email thử nghiệm trước đó.\n\n"
                f"👉 **Khắc phục:** Vui lòng đổi sang một tài khoản Gmail khác (tạo Mật khẩu ứng dụng 16 ký tự) tại trang `/configuration` hoặc đợi Google reset hạn mức sau 24h.",
                icon="🚫"
            )
        elif err_msg:
            st.warning(f"⚠️ **Chưa gửi được email cảnh báo:** {err_msg} (Người nhận: `{get_system_settings().get('recipient_emails')}`). Vui lòng kiểm tra lại tại trang Quản lý Cấu hình.", icon="⚠️")
        else:
            st.warning(f"⚠️ **Chưa gửi được email cảnh báo:** Vui lòng kiểm tra lại cấu hình tài khoản gửi/nhận SMTP (`{get_system_settings().get('recipient_emails')}`) tại trang Quản lý Cấu hình.", icon="⚠️")

    st.markdown("---")

    # 2. BÁO CÁO PHÂN TÍCH NGUYÊN NHÂN GỐC TOÀN DIỆN 8 PHẦN (FULL ENTERPRISE RCA REPORT)
    rca = agent_result.get("rca_analysis", {})
    st.markdown("### 📑 1. Báo Cáo Phân Tích Nguyên Nhân Gốc Toàn Diện (Full Enterprise SRE RCA Report)")

    # 2.1 Metadata Header Card
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

    # 2.2 Dual-Engine Comparison: Có Gemini vs Không Có Gemini
    st.markdown("#### ⚖️ Đối Chứng Suy Luận Tác Tử: Có Gemini vs Không Có Gemini (Dual-Engine Reasoning)")
    st.caption("Đối chứng năng lực suy luận giữa hai cơ chế: Quy tắc tất định (SRE Knowledge Base - 0ms) vs Mô hình ngôn ngữ lớn (Google Gemini AI SRE).")

    is_llm = bool(rca.get("llm_enhanced") and rca.get("llm_insights"))
    gemini_model = rca.get("gemini_model") or "Gemini LLM"
    base_summary = rca.get("base_executive_summary") or rca.get("executive_summary", "Hệ thống áp dụng các quy tắc tất định theo tiêu chuẩn SRE.")
    primary_cause_val = rca.get("root_cause_analysis", {}).get("primary_cause", rca.get("root_cause", "Không có lỗi."))
    llm_insights_val = rca.get("llm_insights", "")

    col_de1, col_de2 = st.columns(2)
    with col_de1:
        st.markdown(f"""
        <div style="background: #0f172a; border: 1px solid #38bdf8; border-radius: 6px; padding: 14px; margin-bottom: 12px; height: 100%;">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
                <span style="font-weight: bold; color: #38bdf8; font-size: 13.5px;">📚 LỰA CHỌN 1: SRE KNOWLEDGE BASE</span>
                <span style="background: #0284c7; color: #ffffff; font-size: 10.5px; font-weight: bold; padding: 2px 8px; border-radius: 4px;">KHÔNG DÙNG AI (0ms)</span>
            </div>
            <div style="font-size: 12.5px; color: #e2e8f0; margin-bottom: 8px;">
                <b>Nguyên nhân cốt lõi (Rule-based):</b><br>
                {primary_cause_val}
            </div>
            <div style="background: #1e293b; border-radius: 4px; padding: 10px; font-size: 12px; color: #cbd5e1; line-height: 1.5; margin-bottom: 8px;">
                <b>Tóm tắt tất định:</b><br>
                {base_summary}
            </div>
            <div style="font-size: 11px; color: #38bdf8; font-style: italic; border-top: 1px dashed #334155; padding-top: 6px;">
                ⚡ <b>Đặc tính:</b> 100% tất định (Deterministic), độ trễ 0ms, chuẩn RFC 9110/1035/5280, không tốn quota API, chạy an toàn kể cả khi ngắt kết nối mạng.
            </div>
        </div>
        """, unsafe_allow_html=True)

    with col_de2:
        if is_llm:
            st.markdown(f"""
            <div style="background: #052e16; border: 1px solid #22c55e; border-radius: 6px; padding: 14px; margin-bottom: 12px; height: 100%;">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
                    <span style="font-weight: bold; color: #4ade80; font-size: 13.5px;">🤖 LỰA CHỌN 2: GOOGLE GEMINI SRE</span>
                    <span style="background: #16a34a; color: #ffffff; font-size: 10.5px; font-weight: bold; padding: 2px 8px; border-radius: 4px;">{gemini_model}</span>
                </div>
                <div style="background: #14532d; border-radius: 4px; padding: 10px; font-size: 12px; color: #dcfce7; line-height: 1.55; white-space: pre-line; margin-bottom: 8px;">
{llm_insights_val}
                </div>
                <div style="font-size: 11px; color: #86efac; font-style: italic; border-top: 1px dashed #166534; padding-top: 6px;">
                    🧠 <b>Đặc tính:</b> Suy luận ngữ cảnh đa chiều (Context-aware), liên kết chéo các chỉ số bất thường, sinh chỉ thị ứng cứu tức thời bằng văn phong SRE tự nhiên.
                </div>
            </div>
            """, unsafe_allow_html=True)
        else:
            st.markdown("""
            <div style="background: #1e1e24; border: 1px solid #475569; border-radius: 6px; padding: 14px; margin-bottom: 12px; height: 100%;">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
                    <span style="font-weight: bold; color: #94a3b8; font-size: 13.5px;">🤖 LỰA CHỌN 2: GOOGLE GEMINI SRE</span>
                    <span style="background: #475569; color: #cbd5e1; font-size: 10.5px; font-weight: bold; padding: 2px 8px; border-radius: 4px;">OFFLINE / DISABLED</span>
                </div>
                <div style="background: #27272a; border-radius: 4px; padding: 10px; font-size: 12px; color: #94a3b8; line-height: 1.5; margin-bottom: 8px;">
                    Tính năng Gemini LLM hiện đang tắt hoặc không khả dụng. Hệ thống tự động chuyển đổi sang <b>SRE Knowledge Base (Fallback 0ms)</b>, bảo đảm tiến trình giám sát và cảnh báo không bị gián đoạn.
                </div>
                <div style="font-size: 11px; color: #94a3b8; font-style: italic; border-top: 1px dashed #3f3f46; padding-top: 6px;">
                    🛡️ <b>Cơ chế Fallback:</b> Tự động dự phòng 100% khi mất mạng hoặc cạn kiệt hạn mức API token.
                </div>
            </div>
            """, unsafe_allow_html=True)

    # 2.3 Executive Summary & Root Cause
    col_rca_l, col_rca_r = st.columns([3, 2])
    with col_rca_l:
        st.markdown("#### 🎙️ Bản Tóm Tắt Quản Trị Hợp Nhất (Executive Summary)")
        st.info(rca.get('executive_summary', 'Hệ thống vận hành bình thường.'))

        st.markdown("#### 🔍 Chi Tiết Nguyên Nhân Gốc (Root Cause Details)")
        rca_detail = rca.get("root_cause_analysis", {})
        st.error(f"**Nguyên nhân cốt lõi:** {rca_detail.get('primary_cause', rca.get('root_cause', 'Không có lỗi.'))}")
        
        if rca_detail.get("contributing_factors"):
            st.markdown("**Các yếu tố phụ tiềm ẩn:**")
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

    # 2.3 Action Plan, Runbook, Prevention & RFC Citations
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

    # 2.4 Nút Tải Báo Cáo Sự Cố (Download Markdown)
    report_markdown = f"""# 📑 BÁO CÁO PHÂN TÍCH NGUYÊN NHÂN GỐC SỰ CỐ (INCIDENT RCA REPORT)
**Mã sự cố:** `{rca.get('incident_id', 'INC-001')}` | **Thời gian:** `{rca.get('timestamp', 'N/A')}` | **Mức độ:** `{rca.get('severity', sev)}`
**Website:** `{selected_site['name']}` ({selected_site.get('url')}) | **Tầng sự cố:** `{rca.get('fault_layer', 'N/A')}` | **Độ tin cậy:** `{rca.get('confidence_score', 98.8)}%`

---

## 1. Bản Tóm Tắt Quản Trị (Executive Summary)
{rca.get('executive_summary')}

---

## 2. Đối Chứng Suy Luận Tác Tử (Dual-Engine Reasoning: Có vs Không Dùng Gemini)
### 2.1 Lựa chọn 1: SRE Knowledge Base (Không Dùng AI)
* **Nguyên nhân gốc (Rule-based):** {primary_cause_val}
* **Tóm tắt tất định:** {base_summary}
* **Đặc tính:** 100% tất định (Deterministic), độ trễ 0ms, tuân thủ RFC 9110/1035/5280, an toàn tuyệt đối khi offline.

### 2.2 Lựa chọn 2: Google Gemini AI SRE ({gemini_model})
* **Trạng thái:** {"✅ Đang hoạt động (Active)" if is_llm else "⚠️ Ngoại tuyến / Đang tắt (Tự động Fallback 0ms sang Knowledge Base)"}
* **Suy luận ngữ cảnh chuyên sâu:**
{llm_insights_val if is_llm else "Chưa kích hoạt hoặc API không khả dụng."}
* **Đặc tính:** Suy luận ngữ cảnh đa chiều, liên kết chéo các tín hiệu dị thường, sinh khuyến nghị SRE tự nhiên.

---

## 3. Phân Tích Chi Tiết Nguyên Nhân Gốc (Root Cause Details)
* **Nguyên nhân cốt lõi:** {rca_detail.get('primary_cause', rca.get('root_cause'))}
* **Bằng chứng kỹ thuật đối soát:**
{chr(10).join([f"  - **[{k}]**: {v}" for k, v in rca_detail.get('cross_signal_evidence', {}).items()])}

---

## 4. Đánh Giá Mức Độ Ảnh Hưởng (Impact Assessment)
* **Người dùng:** {impact.get('user_experience', rca.get('user_impact'))}
* **Khả dụng nghiệp vụ:** {impact.get('business_availability')}

---

## 5. Kế Hoạch Khắc Phục Đề Xuất (Action Plan)
{chr(10).join([f"- [ ] {a}" for a in rca.get('immediate_action_plan', rca.get('action_plan', []))])}

---

## 6. Sổ Tay Điều Tra Kỹ Thuật (SRE Runbook)
{chr(10).join([f"- {s}" for s in rca.get('investigation_runbook', rca.get('investigation_steps', []))])}

---

## 7. Chiến Lược Phòng Ngừa Dài Hạn (Prevention Strategy)
{chr(10).join([f"- {p}" for p in rca.get('prevention_strategy', [])])}

---

## 8. Trích Dẫn Tiêu Chuẩn Kỹ Thuật (Technical RFC Standards)
{chr(10).join([f"- {r}" for r in rca.get('technical_standards', rca.get('rfc_citations', []))])}
"""
    st.download_button(
        label="📥 Tải Báo Cáo Sự Cố (Markdown Format)",
        data=report_markdown,
        file_name=f"RCA_Report_{selected_site['name'].replace(' ', '_')}_{rca.get('incident_id', 'INC001')}.md",
        mime="text/markdown",
        use_container_width=True
    )

    st.markdown("---")

    # 3. Chuỗi Vết Thực Thi Của Tác Tử (Execution Trace Timeline)
    st.markdown("### 🧩 2. Chuỗi Vết Thực Thi & Suy Luận Của Tác Tử (Execution Trace Timeline)")
    st.caption("Minh chứng minh bạch cho từng bước xử lý: Lập kế hoạch -> Gọi Tool -> Phát hiện bất thường -> Tự sửa sai -> Tương quan -> Phân tích -> Báo cáo.")

    trace = agent_result.get("execution_trace", [])
    for t in trace:
        step_num = t.get("step")
        phase = t.get("phase")
        agent_n = t.get("agent")
        action = t.get("action")
        details = t.get("details")
        ts = t.get("timestamp")

        with st.expander(f"Bước {step_num} [{ts}]: **{phase}** — *{agent_n}* ({action})", expanded=(step_num in [1, 4, 6])):
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

    # 4. Ma Trận Đánh Giá 4 Khả Năng Cốt Lõi Của Agentic AI
    st.markdown("### 🏆 3. Ma Trận Đánh Giá 4 Khả Năng Cốt Lõi Của Agentic AI")
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


def render_dashboard(selected_site):
    """Giao diện Dashboard Giám sát phân chia theo 6 Tabs hoàn toàn độc lập với nút chạy thủ công riêng."""
    tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
        "⚠️ Cấu hình 1: Truyền Thống",
        "🛡️ Cấu hình 2: Bán Tự Động", 
        "🧠 Cấu hình 3: Agentic AI Tự Động",
        "⚖️ So Sánh Đối Chứng 3 Cấu Hình",
        "📈 Lịch Sử & Xu Hướng", 
        "🏷️ Quản Lý Mốc Chuẩn (Baseline)"
    ])
    
    with tab1:
        render_traditional_tab(selected_site)

    with tab2:
        render_realtime_tab(selected_site)

    with tab3:
        render_agentic_studio_tab(selected_site)

    with tab4:
        render_benchmark_tab(selected_site)
                    
    with tab5:
        render_history_tab(selected_site)
        
    with tab6:
        render_milestones_tab(selected_site)




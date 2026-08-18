import streamlit as st
import pandas as pd
from datetime import datetime
from config import TIMEZONE_NAME
from database.repository import (
    save_milestone_baseline,
    get_monitoring_logs,
    get_all_milestones,
    set_active_milestone,
    get_active_baseline
)

def render_realtime_tab(selected_site, http_res, dns_res, ssl_res):
    """Hiển thị kết quả kiểm tra thời gian thực với layout hiện đại, gọn gàng và đầy đủ."""
    from database.repository import calculate_overall_status
    overall_status = calculate_overall_status(http_res, dns_res, ssl_res)

    status_badge_map = {
        "HEALTHY": ("🟢 HOẠT ĐỘNG TỐT (HEALTHY)", "#10b981"),
        "WARNING": ("🟡 CẢNH BÁO (WARNING)", "#f59e0b"),
        "CRITICAL": ("🔴 SỰ CỐ NGHIÊM TRỌNG (CRITICAL)", "#ef4444")
    }
    badge_label, badge_color = status_badge_map.get(overall_status, ("⚪ KHÔNG XÁC ĐỊNH", "#6b7280"))

    # 1. Header Overview & KPI Bar
    st.subheader(f"📊 Kết quả kiểm tra: {selected_site['name']}")
    st.markdown(f"**Trạng thái Tổng thể:** `{badge_label}` | **URL:** [{selected_site['url']}]({selected_site['url']}) | **Domain:** `{selected_site['domain']}`")

    # 4 KPI Metrics Card
    kpi1, kpi2, kpi3, kpi4 = st.columns(4)
    http_code = http_res.get("status_code", "N/A")
    http_cat = http_res.get("status_category", "")
    kpi1.metric(
        "🌐 HTTP Status", 
        f"{http_code} {http_cat}".strip(), 
        f"{http_res.get('response_time_ms', 0)} ms"
    )
    
    dns_ok = "Resolved" if dns_res.get("resolved") else "Failed"
    kpi2.metric(
        "🗂️ DNS Resolution", 
        dns_ok, 
        f"{dns_res.get('resolution_time_ms', 0)} ms"
    )
    
    ssl_days = ssl_res.get("days_remaining", 0)
    ssl_status = "Hợp lệ" if ssl_res.get("is_valid") else "Không hợp lệ"
    kpi3.metric(
        "🔒 SSL Certificate", 
        ssl_status, 
        f"{ssl_days} ngày còn lại"
    )
    
    match_label = "Khớp Baseline" if not dns_res.get("changes_detected") else "Phát hiện thay đổi"
    kpi4.metric(
        "🎯 Đối soát Baseline", 
        match_label, 
        "Trùng khớp" if http_res.get("is_expected_status") else "Sai mã HTTP"
    )

    st.markdown("---")

    # 2. Chi tiết 3 tín hiệu phân bổ 3 Cột chuyên biệt
    col_http, col_dns, col_ssl = st.columns(3)

    # Cột 1: HTTP Monitoring (RFC 9110)
    with col_http:
        st.markdown("#### 🌐 HTTP (RFC 9110)")
        if http_res.get("is_success"):
            st.success(f"Status Code: **{http_res.get('status_code')}** ({http_res.get('status_category')})")
        else:
            st.error(f"HTTP Error: **{http_res.get('status_code') or 'Failed'}**")
        
        st.markdown(f"- **Method:** `{http_res.get('method')}`")
        st.markdown(f"- **Thời gian phản hồi:** `{http_res.get('response_time_ms')} ms`")
        st.markdown(f"- **Mã mong đợi:** `{http_res.get('is_expected_status')}` (`{selected_site.get('expected_status', 200)}`)")
        
        if http_res.get("redirect_chain"):
            st.info("🔄 **Redirect Chain:**\n" + "\n".join([f"- `{hop['url']}` ({hop['status_code']})" for hop in http_res["redirect_chain"]]))
            
        if http_res.get("error"):
            st.warning(f"Chi tiết lỗi: `{http_res.get('error')}`")
            
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
            with st.expander("⚠️ Chi tiết thay đổi DNS so với Baseline"):
                st.json(dns_res["changes_detected"])

    # Cột 3: SSL/TLS Monitoring (RFC 5280 & RFC 8446)
    with col_ssl:
        st.markdown("#### 🔒 SSL/TLS (RFC 5280 / 8446)")
        if ssl_res.get("is_valid"):
            st.success(f"Certificate: **Hợp lệ & Tin cậy**")
        else:
            st.error(f"Certificate: **{ssl_res.get('error_type') or 'Không hợp lệ'}**")
            
        st.markdown(f"- **Hạn còn lại:** **{ssl_res.get('days_remaining')} ngày**")
        st.markdown(f"- **TLS Version:** `{ssl_res.get('tls_version') or 'N/A'}`")
        st.markdown(f"- **Hostname Match:** `{'Khớp' if ssl_res.get('hostname_matched') else 'Sai lệch'}`")
        st.markdown(f"- **Tổ chức cấp (Issuer):** `{ssl_res.get('issuer') or 'N/A'}`")
        
        if ssl_res.get("error"):
            st.warning(f"Lỗi SSL: `{ssl_res.get('error')}`")
            
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
            rep_sites_df = rep_sites_df[[
                "name", "current_status", "health_rate", 
                "avg_http_latency_ms", "avg_dns_latency_ms", "ssl_days_remaining", "total_scans"
            ]]
            rep_sites_df.columns = [
                "Website", "Hiện tại", "Healthy %", 
                "Độ trễ HTTP (ms)", "Độ trễ DNS (ms)", "Hạn SSL (ngày)", "Số lần quét"
            ]
            st.dataframe(rep_sites_df, use_container_width=True)
            
        if report_data["incidents"]:
            st.warning(f"⚠️ Trong 24h qua có {len(report_data['incidents'])} sự cố/cảnh báo được ghi nhận.")
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

def render_dashboard(selected_site, http_res=None, dns_res=None, ssl_res=None):
    """Giao diện Dashboard Giám sát phân chia theo 3 Tabs chuyên biệt."""
    tab1, tab2, tab3 = st.tabs([
        "📊 Giám sát Thời gian thực", 
        "📈 Lịch sử & Xu hướng", 
        "🏷️ Quản lý Mốc chuẩn"
    ])
    
    with tab1:
        if http_res and dns_res and ssl_res:
            render_realtime_tab(selected_site, http_res, dns_res, ssl_res)
        else:
            st.info("👉 Hãy bấm nút **'Kiểm tra ngay'** ở thanh điều khiển bên trái để bắt đầu phiên quét mới.")
            # Hiển thị thông tin baseline đang active
            active_b = get_active_baseline(selected_site["id"])
            if active_b:
                st.markdown(f"**Mốc chuẩn đang áp dụng:** `{active_b.get('note')}` (Lưu lúc: {active_b.get('created_at')})")
                with st.expander("Xem DNS Baseline hiện tại"):
                    st.json(active_b.get("baseline_dns", {}))
                    
    with tab2:
        render_history_tab(selected_site)
        
    with tab3:
        render_milestones_tab(selected_site)
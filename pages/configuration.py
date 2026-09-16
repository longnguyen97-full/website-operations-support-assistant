import streamlit as st
import pandas as pd
from datetime import datetime

import config
from database import (
    init_db,
    get_all_websites,
    add_or_update_website,
    delete_website,
    sync_websites_from_json_file,
    get_system_settings,
    update_system_settings,
    sync_settings_from_env,
    create_db_backup,
    get_all_db_backups,
    get_current_db_bytes,
    inspect_sqlite_bytes,
    restore_db_from_bytes,
    restore_db_from_file,
    delete_db_backup,
    generate_periodic_report_data
)
import streamlit.components.v1 as components
from notifications.email_service import (
    send_test_email,
    send_periodic_report_email,
    build_incident_alert_html,
    build_periodic_report_html
)
from tools.gemini_client import test_gemini_connection
from scheduler import (
    get_scheduler_info,
    update_scheduler_interval,
    stop_background_scheduler,
    run_monitors_now
)
from scheduler.monitor_scheduler import resume_background_scheduler

# --- Cấu hình trang ---
st.set_page_config(
    layout="wide",
    page_title="Quản lý Cấu hình - Agentic AI Monitoring Assistant",
    page_icon="⚙️"
)

def render_configuration_page():
    init_db()
    settings = get_system_settings()

    st.title("⚙️ Quản lý Cấu hình Hệ thống (System Configuration)")
    st.markdown("Toàn bộ cấu hình vận hành, mục tiêu giám sát, bộ lập lịch và thông báo được lưu trữ trực tiếp trong CSDL SQLite (`monitoring.db`).")

    # ==========================================
    # PHẦN 1: QUẢN LÝ TARGET WEBSITES
    # ==========================================
    st.markdown("## 🎯 1. Quản lý Mục tiêu Giám sát (Target Websites)")
    
    col_w1, col_w2 = st.columns([1, 2])
    with col_w1:
        st.markdown("#### ➕ Thêm / Cập nhật Website")
        with st.form("add_website_form"):
            w_name = st.text_input("Tên Website:", placeholder="Google")
            w_url = st.text_input("URL đầy đủ:", placeholder="https://www.google.com")
            w_domain = st.text_input("Domain:", placeholder="google.com")
            w_exp_status = st.number_input("Mã HTTP kỳ vọng:", min_value=100, max_value=599, value=200)
            
            btn_add_site = st.form_submit_button("Lưu Website Vào CSDL", type="primary")
            if btn_add_site:
                if w_name and w_url and w_domain:
                    add_or_update_website(w_name.strip(), w_url.strip(), w_domain.strip(), int(w_exp_status))
                    st.success(f"✅ Đã lưu website '{w_name}' vào CSDL!")
                    st.rerun()
                else:
                    st.error("Vui lòng điền đầy đủ Tên, URL và Domain.")

        st.markdown("---")
        st.markdown("#### 🔄 Nạp Dữ liệu từ File Cấu hình")
        if st.button("📥 Đồng bộ toàn bộ Target Websites từ target_websites.json", use_container_width=True, type="secondary"):
            with st.spinner("Đang nạp và đồng bộ danh sách website vào CSDL SQLite..."):
                sync_res = sync_websites_from_json_file()
                if sync_res["success"]:
                    st.success(f"🎉 {sync_res['message']}")
                    st.rerun()
                else:
                    st.error(f"❌ {sync_res['message']}")

    with col_w2:
        st.markdown("#### 📋 Danh sách Website đang được giám sát")
        current_websites = get_all_websites()
        if current_websites:
            w_df = pd.DataFrame(current_websites)[["id", "name", "url", "domain", "expected_status"]]
            w_df.columns = ["ID", "Tên Website", "URL", "Domain", "HTTP Kỳ vọng"]
            st.dataframe(w_df, use_container_width=True)

            # Xóa website
            with st.expander("🗑️ Xóa Website khỏi danh mục"):
                del_site_id = st.selectbox(
                    "Chọn website cần xóa:", 
                    options=[w["id"] for w in current_websites],
                    format_func=lambda x: next((f"ID #{w['id']} - {w['name']} ({w['domain']})" for w in current_websites if w["id"] == x), str(x))
                )
                if st.button("Xác nhận Xóa Website", type="secondary"):
                    delete_website(del_site_id)
                    st.success(f"Đã xóa website ID #{del_site_id} thành công!")
                    st.rerun()
        else:
            st.info("Chưa có website nào trong CSDL.")

    st.markdown("---")

    # ==========================================
    # PHẦN 2: ĐIỀU KHIỂN & CẤU HÌNH APSCHEDULER
    # ==========================================
    st.markdown("## ⏱️ 2. Bộ lập lịch Quét Tự động (APScheduler)")
    sched_info = get_scheduler_info()
    
    c_s1, c_s2, c_s3 = st.columns(3)
    c_s1.metric(
        "Trạng thái Bộ lập lịch", 
        "🟢 Đang Chạy Tự Động" if sched_info["is_running"] else "🔴 Đã Dừng Quét"
    )
    cur_sec = sched_info['interval_seconds']
    cur_display = (
        f"{cur_sec // 3600} tiếng ({cur_sec:,}s)" if cur_sec >= 3600 
        else (f"{cur_sec // 60} phút ({cur_sec}s)" if cur_sec >= 60 else f"{cur_sec} giây")
    )
    c_s2.metric("Chu kỳ quét hiện tại", cur_display)
    c_s3.metric("Tổng số lần quét nền", f"{sched_info['total_runs']} lần")

    if sched_info["is_running"] and sched_info.get("next_run_time"):
        st.caption(f"🕒 **Lần quét tiếp theo (UTC+7):** `{sched_info['next_run_time']}`")
    elif not sched_info["is_running"]:
        st.caption("🛑 **Trạng thái:** Hệ thống đang dừng quét nền tự động. Nhấp '▶️ Bắt Đầu Quét' để tiếp tục giám sát theo chu kỳ.")
    if sched_info.get("last_run_time"):
        st.caption(f"✅ **Lần quét gần nhất:** `{str(sched_info['last_run_time']).replace('T', ' ')[:19]}`")

    # Điều khiển Scheduler
    col_ctl1, col_ctl2, col_ctl3 = st.columns([2, 1, 1])
    with col_ctl1:
        sched_options = [60, 300, 600, 1800, 3600, 7200, 14400, 28800, 86400]
        cur_val = sched_info["interval_seconds"]
        if cur_val not in sched_options:
            sched_options = sorted(sched_options + [cur_val])

        def _fmt_interval(x):
            if x < 60:
                return f"{x} giây"
            elif x < 3600:
                return f"{x//60} phút"
            else:
                h = x / 3600
                return f"{int(h) if h.is_integer() else h} tiếng"

        new_sched_interval = st.select_slider(
            "Thay đổi chu kỳ quét định kỳ:",
            options=sched_options,
            value=cur_val,
            format_func=_fmt_interval,
            key="sched_select_slider"
        )
        if new_sched_interval != sched_info["interval_seconds"]:
            update_scheduler_interval(new_sched_interval, persist_db=True)
            st.toast(f"Đã đổi chu kỳ quét thành {_fmt_interval(new_sched_interval)} ({new_sched_interval}s) và lưu vào CSDL!", icon="⏱️")
            st.rerun()

        if st.button("💾 Lưu Chu Kỳ Quét Vào CSDL", use_container_width=True, type="secondary"):
            update_scheduler_interval(new_sched_interval, persist_db=True)
            st.success(f"✅ Đã lưu chu kỳ quét {_fmt_interval(new_sched_interval)} ({new_sched_interval:,} giây) vào CSDL thành công!")
            st.toast("Đã lưu chu kỳ quét vào CSDL!", icon="💾")
            st.rerun()

    with col_ctl2:
        st.write("&nbsp;")
        if sched_info["is_running"]:
            if st.button("🛑 Dừng Quét", use_container_width=True, help="Dừng tiến trình quét nền tự động"):
                stop_background_scheduler()
                st.toast("Đã dừng quét nền tự động!", icon="🛑")
                st.rerun()
        else:
            if st.button("▶️ Bắt Đầu Quét", use_container_width=True, type="primary", help="Kích hoạt lại tiến trình quét tự động"):
                resume_background_scheduler()
                st.toast("Đã kích hoạt quét nền tự động!", icon="▶️")
                st.rerun()

    with col_ctl3:
        st.write("&nbsp;")
        if st.button("⚡ Quét Ngay Tất Cả", use_container_width=True):
            with st.spinner("Đang chạy kiểm tra toàn bộ website..."):
                run_monitors_now()
                st.toast("Đã hoàn tất quét tất cả website!", icon="⚡")
                st.rerun()

    st.markdown("---")

    # ==========================================
    # PHẦN 3: CẤU HÌNH EMAIL, BÁO CÁO & THAM SỐ
    # ==========================================
    col_hdr1, col_hdr2 = st.columns([3, 1])
    with col_hdr1:
        st.markdown("## 📧 3. Cấu hình Email, Báo cáo Định kỳ & Cảnh báo")
    with col_hdr2:
        if st.button("📥 Nạp Lại từ File .env", use_container_width=True):
            sync_settings_from_env()
            st.toast("Đã nạp toàn bộ cấu hình từ file .env vào Database!", icon="📥")
            st.rerun()

    with st.expander("ℹ️ Hướng dẫn lấy Mật khẩu ứng dụng (App Password) cho Gmail"):
        st.markdown("""
        1. Bật **Xác thực 2 bước (2-Step Verification)** trên tài khoản Google.
        2. Truy cập: [Google App Passwords](https://myaccount.google.com/apppasswords).
        3. Tạo mật khẩu ứng dụng mới với tên `Website Monitor`.
        4. Sao chép chuỗi mật khẩu 16 ký tự vào ô **Mật khẩu ứng dụng (App Password)** bên dưới.
        """)

    with st.form("dynamic_system_config_form"):
        # 1. Email & SMTP
        st.markdown("#### A. Thông số Máy chủ SMTP")
        is_enabled = st.toggle(
            "🔔 Kích hoạt tính năng Dịch vụ Email (Gửi báo cáo & cảnh báo)", 
            value=bool(settings.get("is_enabled", 0))
        )
        
        c1, c2, c3 = st.columns([2, 1, 1])
        smtp_server = c1.text_input("SMTP Server:", value=settings.get("smtp_server", config.DEFAULT_SMTP_SERVER))
        smtp_port = c2.number_input("Port:", min_value=1, max_value=65535, value=int(settings.get("smtp_port", config.DEFAULT_SMTP_PORT)))
        use_tls = c3.checkbox("Sử dụng TLS / STARTTLS", value=bool(settings.get("use_tls", config.DEFAULT_USE_TLS)))

        c4, c5 = st.columns(2)
        sender_email = c4.text_input(
            "Sender Email (Email gửi):", 
            value=settings.get("sender_email", config.DEFAULT_SENDER_EMAIL), 
            placeholder="admin@gmail.com"
        )
        sender_password = c5.text_input(
            "App Password (Mật khẩu ứng dụng):", 
            value=settings.get("sender_password", config.DEFAULT_SENDER_PASSWORD), 
            type="password", 
            placeholder="16 ký tự app password"
        )
        
        recipient_emails = st.text_area(
            "Danh sách Email Người nhận Báo cáo & Cảnh báo (phân cách bởi dấu phẩy):", 
            value=settings.get("recipient_emails", config.DEFAULT_RECIPIENT_EMAILS),
            placeholder="devops@company.com, admin@company.com"
        )

        # 2. Báo cáo định kỳ
        st.markdown("#### B. 📊 Báo cáo Sức khỏe Định kỳ Hàng ngày (Daily Health Digest)")
        c6, c7 = st.columns([2, 1])
        enable_daily_report = c6.checkbox(
            "✅ Tự động tổng hợp và gửi Báo cáo Sức khỏe hàng ngày qua Email", 
            value=bool(settings.get("enable_daily_report", 0))
        )
        daily_report_time = c7.text_input(
            "Khung giờ gửi hàng ngày (HH:MM):", 
            value=settings.get("daily_report_time", config.DEFAULT_DAILY_REPORT_TIME), 
            placeholder="08:00"
        )
        st.caption("ℹ️ Báo cáo sẽ thống kê chi tiết tỷ lệ Uptime %, độ trễ trung bình, hạn chứng chỉ SSL và các sự cố trong 24 giờ qua.")

        # 3. Cảnh báo Sự cố
        st.markdown("#### C. 🚨 Quy tắc Cảnh báo Sự cố Tức thời (Incident Alerts)")
        c8, c9, c10 = st.columns(3)
        notify_critical = c8.checkbox("🚨 Lỗi CRITICAL (Website Down, SSL Expired, DNS Failed)", value=bool(settings.get("notify_on_critical", 1)))
        notify_warning = c9.checkbox("⚠️ Cảnh báo WARNING (SSL sắp hết hạn)", value=bool(settings.get("notify_on_warning", 1)))
        notify_recovery = c10.checkbox("✅ Thông báo PHỤC HỒI (Recovery)", value=bool(settings.get("notify_on_recovery", 1)))

        cooldown = st.number_input(
            "Thời gian chờ giữa các lần gửi cảnh báo lặp lại (Cooldown phút):", 
            min_value=1, max_value=1440, 
            value=int(settings.get("cooldown_minutes", config.DEFAULT_COOLDOWN_MINUTES))
        )

        # 4. Tham số Vận hành
        st.markdown("#### D. ⏱️ Tham số Vận hành & Lưu trữ Dữ liệu")
        c11, c12, c13 = st.columns(3)
        active_sched_info = get_scheduler_info()
        active_interval_val = int(active_sched_info.get("interval_seconds") or settings.get("scheduler_interval_seconds", config.DEFAULT_SCHEDULER_INTERVAL_SECONDS))
        sched_interval_val = c11.number_input(
            "Chu kỳ quét định kỳ mặc định (giây):", 
            min_value=10, max_value=86400, step=60,
            value=active_interval_val,
            help="14400 giây = 4 tiếng; 86400 giây = 24 tiếng; 3600 giây = 1 tiếng; 600 giây = 10 phút. Đồng bộ cùng Mục 2."
        )
        retention_days = c12.number_input(
            "Số ngày lưu giữ lịch sử logs (Data Retention):", 
            min_value=1, max_value=365, 
            value=int(settings.get("data_retention_days", config.DATA_RETENTION_DAYS))
        )
        ssl_warn_days = c13.number_input(
            "Ngưỡng cảnh báo hạn chứng chỉ SSL (ngày):", 
            min_value=1, max_value=90, 
            value=int(settings.get("ssl_warning_days", config.SSL_EXPIRY_WARNING_DAYS))
        )

        # 5. Cấu hình Timeout Mạng (Network Probe Timeouts)
        st.markdown("#### E. 🌐 Cấu hình Thời gian Chờ Mạng (Network Timeout Probes)")
        st.caption("Cấu hình giới hạn thời gian (giây) tối đa mà hệ thống chờ đợi phản hồi từ mục tiêu trước khi đánh dấu là Timeout.")
        c14, c15, c16 = st.columns(3)
        http_timeout_val = c14.number_input(
            "HTTP Request Timeout (giây):",
            min_value=1.0, max_value=120.0, step=0.5,
            value=float(settings.get("http_timeout_seconds", config.HTTP_TIMEOUT_SECONDS)),
            help="Thời gian tối đa chờ phản hồi HTTP Request trước khi ném ngoại lệ Timeout."
        )
        dns_timeout_val = c15.number_input(
            "DNS Resolver Timeout (giây):",
            min_value=1.0, max_value=60.0, step=0.5,
            value=float(settings.get("dns_timeout_seconds", config.DNS_TIMEOUT_SECONDS)),
            help="Thời gian tối đa chờ phân giải tên miền DNS trước khi đánh dấu thất bại."
        )
        ssl_timeout_val = c16.number_input(
            "SSL/TLS Handshake Timeout (giây):",
            min_value=1.0, max_value=60.0, step=0.5,
            value=float(settings.get("ssl_timeout_seconds", config.SSL_TIMEOUT_SECONDS)),
            help="Thời gian tối đa chờ thiết lập bắt tay mã hóa SSL/TLS socket."
        )

        # 6. Cấu hình Gemini LLM
        st.markdown("#### F. 🤖 Cấu hình Mô hình Ngôn ngữ Lớn (Google Gemini LLM Reasoning)")
        st.caption("Tích hợp Gemini LLM cho Tác tử Phân tích Sự cố (Incident Analysis Agent) để tự động sinh bản tóm tắt nguyên nhân gốc (RCA), đánh giá rủi ro chuỗi và khuyến nghị Runbook bằng ngôn ngữ tự nhiên.")

        llm_enabled_val = st.toggle(
            "🧠 Kích hoạt Google Gemini AI cho Incident Analysis Agent",
            value=bool(settings.get("llm_enabled", 0)),
            help="Khi bật, hệ thống sẽ gọi Gemini API để phân tích chuyên sâu sự cố. Khi tắt hoặc khi mất mạng, hệ thống tự động fallback về Knowledge Base & SRE Rules."
        )

        c_llm1, c_llm2 = st.columns([1, 2])
        model_options = [
            "gemini-flash-latest",
            "gemini-flash-lite-latest",
            "gemini-3.7-flash",
            "gemini-3.6-flash",
            "gemini-3.5-flash",
            "gemini-3-flash-preview"
        ]
        curr_model = settings.get("gemini_model", config.DEFAULT_GEMINI_MODEL)
        model_idx = model_options.index(curr_model) if curr_model in model_options else 0
        gemini_model_val = c_llm1.selectbox(
            "Chọn mô hình Gemini:",
            options=model_options,
            index=model_idx,
            help="gemini-flash-latest: Mô hình tự động trỏ tới bản Flash mới nhất của Google, tối ưu cho giám sát SRE."
        )
        gemini_key_val = c_llm2.text_input(
            "Gemini API Key:",
            value=settings.get("gemini_api_key", config.DEFAULT_GEMINI_API_KEY),
            type="password",
            placeholder="Dán mã API Key của bạn (ví dụ: AIzaSy...)",
            help="Khóa API lấy từ Google AI Studio (miễn phí)."
        )

        with st.expander("ℹ️ Hướng dẫn nhận Gemini API Key miễn phí từ Google AI Studio"):
            st.markdown("""
            1. Truy cập vào **[Google AI Studio - API Keys](https://aistudio.google.com/app/apikey)**.
            2. Đăng nhập bằng tài khoản Google cá nhân hoặc tổ chức.
            3. Nhấp vào nút **Create API Key** (Tạo khóa API mới).
            4. Sao chép chuỗi mã API (`AIzaSy...`) và dán vào ô **Gemini API Key** ở trên.
            5. Nhấp nút **Lưu Toàn Bộ Cấu Hình Động Vào CSDL** và sử dụng nút **Kiểm Tra Kết Nối Gemini API** bên dưới để xác thực.
            """)

        btn_save = st.form_submit_button("💾 Lưu Toàn Bộ Cấu Hình Động Vào CSDL", type="primary")
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
                "daily_report_time": daily_report_time,
                "scheduler_interval_seconds": sched_interval_val,
                "scheduler_enabled": 1 if active_sched_info.get("is_running") else 0,
                "data_retention_days": retention_days,
                "ssl_warning_days": ssl_warn_days,
                "http_timeout_seconds": http_timeout_val,
                "dns_timeout_seconds": dns_timeout_val,
                "ssl_timeout_seconds": ssl_timeout_val,
                "monitoring_mode": "AGENTIC",
                "latency_threshold_ms": float(settings.get("latency_threshold_ms", 2000.0)),
                "gemini_api_key": gemini_key_val.strip(),
                "gemini_model": gemini_model_val.strip(),
                "llm_enabled": llm_enabled_val
            }
            update_system_settings(updated_data)
            update_scheduler_interval(int(sched_interval_val), persist_db=True)
            st.success("✅ Đã cập nhật và lưu cấu hình động thành công vào Database!")
            st.toast("Đã lưu cấu hình thành công!", icon="💾")
            st.rerun()

    # Thao tác gửi email và kiểm thử
    st.markdown("#### 🚀 Thao tác Kiểm thử Nhanh")
    col_act1, col_act2, col_act3 = st.columns(3)
    if col_act1.button("📊 Gửi Báo Cáo Định Kỳ 24h", type="primary", use_container_width=True):
        current_cfg = get_system_settings()
        with st.spinner("Đang tổng hợp dữ liệu 24h qua và gửi email báo cáo..."):
            success, msg = send_periodic_report_email(hours=24, settings=current_cfg)
            if success:
                st.success("🎉 " + msg)
            else:
                st.error("❌ " + msg)

    if col_act2.button("🧪 Kiểm Tra Kết Nối SMTP", use_container_width=True):
        current_cfg = get_system_settings()
        with st.spinner("Đang kết nối tới máy chủ SMTP và gửi email thử nghiệm..."):
            success, msg = send_test_email(current_cfg)
            if success:
                st.success("🎉 " + msg)
            else:
                st.error("❌ " + msg)

    if col_act3.button("🤖 Kiểm Tra Kết Nối Gemini API", use_container_width=True):
        current_cfg = get_system_settings()
        target_key = (current_cfg.get("gemini_api_key") or gemini_key_val).strip()
        target_model = current_cfg.get("gemini_model") or gemini_model_val
        with st.spinner("Đang gửi lệnh kiểm tra tới Google Gemini API..."):
            res = test_gemini_connection(api_key=target_key, model=target_model)
            if res["success"]:
                st.success("🎉 " + res["message"])
            else:
                st.error("❌ " + res["message"])

    st.markdown("---")

    # ==========================================
    # PHẦN 3.1: XEM TRƯỚC MẪU EMAIL THÔNG BÁO (LIVE EMAIL PREVIEW)
    # ==========================================
    st.markdown("## 📨 3.1. Xem Trước Cấu Trúc & Nội Dung 2 Mẫu Email")
    st.markdown("Giúp Quản trị viên nắm bắt trực quan mẫu giao diện HTML, các trường số liệu, mã màu trạng thái và nội dung email được gửi về hòm thư mà không cần phải kích hoạt gửi email thật.")

    with st.expander("👁️ Mở Bảng Xem Trước Giao Diện Mẫu Email (Email Templates Live Preview)", expanded=True):
        tab_tpl1, tab_tpl2 = st.tabs([
            "📊 Mẫu 1: Báo Cáo Sức Khỏe Định Kỳ Hàng Ngày (Daily Health Digest)",
            "🚨 Mẫu 2: Cảnh Báo Sự Cố Khẩn Cấp (Emergency Incident Alert)"
        ])

        with tab_tpl1:
            st.markdown("##### 📌 Tiêu Đề Email Dự Kiến:")
            st.code("📊 [Báo cáo Định kỳ 24h] Tổng hợp Sức khỏe Hệ thống Website", language="text")
            st.caption("Báo cáo tự động tổng hợp toàn bộ website đang giám sát, tỷ lệ SLA Uptime, độ trễ mạng HTTP/DNS, hạn chứng chỉ SSL và danh sách sự cố trong 24 giờ qua.")
            
            try:
                live_rep_data = generate_periodic_report_data(hours=24)
                preview_digest_html = build_periodic_report_html(live_rep_data)
            except Exception as e:
                preview_digest_html = f"<div style='padding:20px; color:red;'>Lỗi nạp dữ liệu báo cáo: {e}</div>"

            components.html(preview_digest_html, height=650, scrolling=True)

        with tab_tpl2:
            st.caption("Chọn kịch bản sự cố mô phỏng bên dưới để xem trước mẫu email cảnh báo tương ứng:")
            col_sc1, col_sc2 = st.columns([2, 3])
            with col_sc1:
                scenario = st.selectbox(
                    "Chọn kịch bản sự cố mô phỏng:",
                    options=[
                        "🚨 CRITICAL: HTTP 500 Backend Crash (Server Error)",
                        "🚨 CRITICAL: Lỗi Phân giải Tên miền (DNS Outage)",
                        "🚨 CRITICAL: Chứng chỉ SSL Hết hạn (SSL Expired)",
                        "⚠️ WARNING: Chứng chỉ SSL Sắp hết hạn (< 14 ngày)",
                        "✅ RECOVERY: Hệ thống đã khôi phục hoạt động"
                    ]
                )
            
            now_str = datetime.now(config.TZ_VN).strftime("%d/%m/%Y %H:%M:%S")
            sample_site_name = "Site 001 (site-001.test)"
            sample_site_url = "https://site-001.test"

            if "HTTP 500" in scenario:
                p_status = "CRITICAL"
                p_http = {"status_code": 500, "status_category": "5xx Server Error", "response_time_ms": 145.2, "is_expected_status": False, "error": "Internal Server Error (Database connection pool exhausted)"}
                p_dns = {"resolved": True, "resolution_time_ms": 4.8}
                p_ssl = {"is_valid": True, "days_remaining": 89, "tls_version": "TLSv1.3"}
                p_subject = f"🚨 [CRITICAL] Cảnh báo khẩn cấp sự cố Website '{sample_site_name}'"
            elif "DNS" in scenario:
                p_status = "CRITICAL"
                p_http = {"status_code": None, "status_category": "Error", "response_time_ms": 0.0, "is_expected_status": False, "error": "Failed to resolve domain name (NXDOMAIN)"}
                p_dns = {"resolved": False, "resolution_time_ms": 0.0, "error": "DNS query failed: NXDOMAIN"}
                p_ssl = {"can_connect": False, "is_valid": False, "days_remaining": 0}
                p_subject = f"🚨 [CRITICAL] Cảnh báo khẩn cấp sự cố Website '{sample_site_name}'"
            elif "Hết hạn" in scenario:
                p_status = "CRITICAL"
                p_http = {"status_code": 200, "status_category": "2xx Success", "response_time_ms": 82.0, "is_expected_status": True}
                p_dns = {"resolved": True, "resolution_time_ms": 6.1}
                p_ssl = {"is_valid": False, "days_remaining": 0, "error_title": "Certificate Expired", "error": "Chứng chỉ đã quá hạn sử dụng", "tls_version": "TLSv1.3"}
                p_subject = f"🚨 [CRITICAL] Cảnh báo khẩn cấp sự cố Website '{sample_site_name}'"
            elif "WARNING" in scenario:
                p_status = "WARNING"
                p_http = {"status_code": 200, "status_category": "2xx Success", "response_time_ms": 65.4, "is_expected_status": True}
                p_dns = {"resolved": True, "resolution_time_ms": 5.0}
                p_ssl = {"is_valid": True, "days_remaining": 7, "tls_version": "TLSv1.3"}
                p_subject = f"⚠️ [WARNING] Cảnh báo sự cố Website '{sample_site_name}'"
            else:
                p_status = "HEALTHY"
                p_http = {"status_code": 200, "status_category": "2xx Success", "response_time_ms": 42.1, "is_expected_status": True}
                p_dns = {"resolved": True, "resolution_time_ms": 3.9}
                p_ssl = {"is_valid": True, "days_remaining": 89, "tls_version": "TLSv1.3"}
                p_subject = f"✅ [Phục hồi] Website '{sample_site_name}' đã hoạt động bình thường trở lại"

            # Mock dữ liệu RCA chuẩn Agentic AI phục vụ Preview trực quan
            sample_rca = {
                "incident_id": "INC-20260905-001",
                "fault_layer": "Application / Backend DB" if "HTTP 500" in scenario else ("Network / DNS" if "DNS" in scenario else "Security / TLS"),
                "fault_category": "BACKEND_500" if "HTTP 500" in scenario else ("DNS_FAILURE" if "DNS" in scenario else "SSL_EXPIRED"),
                "confidence_score": 98.8,
                "root_cause_analysis": {
                    "primary_cause": "Ngoại lệ gián đoạn kết nối cơ sở dữ liệu: DatabaseConnectionTimeout tại MySQL (10.0.0.5:3306) khiến tiến trình backend trả về HTTP 500." if "HTTP 500" in scenario else ("Không tìm thấy bản ghi A hợp lệ (NXDOMAIN) cho tên miền." if "DNS" in scenario else "Chứng chỉ X.509 quá hạn 358 ngày."),
                    "contributing_factors": [
                        "Cạn kiệt Connection Pool của Database do lưu lượng tăng đột biến.",
                        "Tắc nghẽn mạng nội bộ giữa Web Server và CSDL máy chủ.",
                        "Thiếu cơ chế Circuit Breaker tự ngắt khi DB quá tải."
                    ] if "HTTP 500" in scenario else ["Cấu hình DNS Authoritative bị gián đoạn."],
                    "cross_signal_evidence": {
                        "HTTP": "Status Code: 500 (5xx Server Error) | Response Time: 145.2ms | Error: Internal Server Error",
                        "DNS": "Status: Resolved | Resolution Time: 4.8ms | Records A: ['127.0.0.1']",
                        "SSL/TLS": "Status: VALID | Issuer: Let's Encrypt | Days Remaining: 89 days",
                        "Performance": "Total Load Time: 145.2ms | Grade: Critical",
                        "DOM": "Root element found, dynamic checkout block empty"
                    }
                },
                "immediate_action_plan": [
                    "Khởi động lại ngay tiến trình Backend hoặc container ứng dụng.",
                    "Kiểm tra lại thông tin cấu hình kết nối DB (Host, Port, User, Password) trong file .env.",
                    "Kiểm tra sức khỏe cụm Database và tăng số lượng kết nối tối đa (Max Connections Pool)."
                ] if "HTTP 500" in scenario else ["Cập nhật lại bản ghi A trên DNS Server."],
                "investigation_runbook": [
                    "systemctl status mysql",
                    "tail -n 100 /var/log/nginx/error.log",
                    "mysqladmin ping -h 10.0.0.5 -u root -p"
                ] if "HTTP 500" in scenario else ["dig @8.8.8.8 site-001.test A"],
                "impact_assessment": {
                    "user_experience": "Toàn bộ người dùng truy cập nhận thông báo lỗi 500, không thể xem sản phẩm hoặc đặt hàng.",
                    "business_availability": "Gián đoạn luồng nghiệp vụ kinh doanh, suy giảm độ tin cậy và gây thiệt hại doanh thu trực tiếp."
                },
                "prevention_strategy": [
                    "Bổ sung khối try/catch toàn cục và Middleware xử lý lỗi tập trung.",
                    "Thiết lập cơ chế Circuit Breaker & Retry có giới hạn đối với kết nối Database.",
                    "Tích hợp công cụ giám sát APM (OpenTelemetry) để tự động bắt Exception."
                ],
                "technical_standards": ["RFC 9110 (HTTP 500)", "RFC 1035 (DNS)", "SRE Golden Signals: Errors"],
                "base_executive_summary": "Phát hiện sự cố nghiêm trọng tại tầng Backend: Máy chủ trả về HTTP 500 do Database Timeout. Hệ thống áp dụng quy tắc tất định theo chuẩn RFC 9110 để kích hoạt cảnh báo cấp độ CRITICAL.",
                "llm_enhanced": True,
                "gemini_model": "gemini-flash-lite-latest",
                "llm_insights": "• Phân tích chuỗi nguyên nhân: Lỗi HTTP 500 bắt nguồn từ việc Connection Pool MySQL bị bão hòa trong đợt tải cao điểm, làm gián đoạn API gateway.\n• Đánh giá tương quan: Bằng chứng DNS và SSL đều hoàn hảo (Resolved 4.8ms, TLS 1.3 hợp lệ 89 ngày), xác nhận 100% sự cố cô lập tại cụm Application/DB nội bộ, không phải do hạ tầng mạng biên hay tấn công bên ngoài.\n• Đề xuất ưu tiên P0: Tạm thời scale up pool size lên 200 connection và kích hoạt Nginx rate limiting để giảm áp lực lên cụm DB trước khi khởi động lại dịch vụ."
            }

            with col_sc2:
                st.markdown("##### 📌 Tiêu Đề Email Dự Kiến:")
                st.code(p_subject, language="text")

            preview_alert_html = build_incident_alert_html(
                site_name=sample_site_name,
                site_url=sample_site_url,
                overall_status=p_status,
                http_res=p_http,
                dns_res=p_dns,
                ssl_res=p_ssl,
                timestamp=now_str,
                rca_report=sample_rca if p_status != "HEALTHY" else None
            )
            components.html(preview_alert_html, height=750, scrolling=True)

    st.markdown("---")

    # ==========================================
    # PHẦN 4: SAO LƯU & KHÔI PHỤC CƠ SỞ DỮ LIỆU
    # ==========================================
    st.markdown("## 💾 4. Sao lưu & Khôi phục Cơ sở Dữ liệu (Database Backup & Restore)")
    st.markdown("Toàn bộ cấu hình hệ thống, danh mục website, các mốc baseline chuẩn và lịch sử logs giám sát được lưu trữ an toàn trong SQLite (`data/monitoring.db`). Bạn có thể tải về bản sao lưu dự phòng hoặc khôi phục dữ liệu bất cứ lúc nào.")

    col_bk1, col_bk2 = st.columns(2)

    with col_bk1:
        st.markdown("### 📥 Sao lưu Cơ sở Dữ liệu (Backup)")
        st.caption("Tải file `.db` về máy hoặc tạo bản snapshot an toàn vào thư mục `data/backups/`.")

        # 1. Nút tải trực tiếp CSDL hiện tại
        db_raw_bytes = get_current_db_bytes()
        now_ts = datetime.now(config.TZ_VN).strftime("%Y%m%d_%H%M%S")
        if db_raw_bytes:
            st.download_button(
                label="⬇️ Tải xuống file CSDL hiện tại (monitoring.db)",
                data=db_raw_bytes,
                file_name=f"monitoring_backup_{now_ts}.db",
                mime="application/x-sqlite3",
                use_container_width=True,
                type="primary"
            )
        else:
            st.warning("⚠️ Không thể đọc file cơ sở dữ liệu hiện tại.")

        # 2. Tạo bản snapshot cục bộ
        with st.form("create_snapshot_form"):
            st.markdown("##### 📌 Tạo Snapshot Cục bộ (Local Snapshot)")
            snap_note = st.text_input(
                "Ghi chú bản sao lưu (tùy chọn):",
                placeholder="VD: truoc_khi_nang_cap_he_thong",
                help="Ghi chú sẽ được gắn vào tên file sao lưu để tiện nhận diện."
            )
            btn_create_snap = st.form_submit_button("Tạo Bản Snapshot Cục bộ", use_container_width=True)
            if btn_create_snap:
                success, snap_msg, path = create_db_backup(custom_name=snap_note)
                if success:
                    st.success(f"✅ {snap_msg}")
                    st.rerun()
                else:
                    st.error(f"❌ {snap_msg}")

        # 3. Danh sách các bản snapshot cục bộ
        all_backups = get_all_db_backups()
        with st.expander(f"📁 Quản lý các bản sao lưu cục bộ ({len(all_backups)} bản lưu)", expanded=False):
            if all_backups:
                for idx, bk in enumerate(all_backups):
                    tag = "🛡️ [Safety Auto-Backup]" if bk["is_safety"] else "📦 [Manual Snapshot]"
                    st.markdown(f"**{idx + 1}. {tag} `{bk['filename']}`**")
                    st.caption(f"📅 Thời gian: {bk['created_time']} | 💾 Dung lượng: {bk['size_kb']} KB")
                    
                    c_btn1, c_btn2 = st.columns([1, 1])
                    with c_btn1:
                        if st.button(f"♻️ Khôi phục bản này", key=f"restore_local_{bk['filename']}", use_container_width=True):
                            ok, r_msg = restore_db_from_file(bk["path"])
                            if ok:
                                st.success(r_msg)
                                st.rerun()
                            else:
                                st.error(r_msg)
                    with c_btn2:
                        if st.button(f"🗑️ Xóa", key=f"del_bk_{bk['filename']}", type="secondary", use_container_width=True):
                            ok, d_msg = delete_db_backup(bk["path"])
                            if ok:
                                st.success(d_msg)
                                st.rerun()
                            else:
                                st.error(d_msg)
                    st.markdown("---")
            else:
                st.info("Chưa có bản sao lưu cục bộ nào trong thư mục `data/backups/`.")

    with col_bk2:
        st.markdown("### 📤 Khôi phục Cơ sở Dữ liệu (Restore)")
        st.caption("Tải lên file `.db` hoặc `.sqlite` để nạp lại dữ liệu vào hệ thống.")

        uploaded_db = st.file_uploader(
            "Chọn file CSDL SQLite cần khôi phục:",
            type=["db", "sqlite"],
            help="Chỉ chấp nhận file định dạng SQLite có chứa schema hợp lệ của hệ thống."
        )

        if uploaded_db is not None:
            db_bytes = uploaded_db.getvalue()
            is_valid, inspect_msg, stats = inspect_sqlite_bytes(db_bytes)

            if is_valid:
                st.success("✅ File CSDL hợp lệ và tương thích hoàn toàn!")
                st.markdown(f"""
                - **📊 Số Website mục tiêu:** `{stats.get('website_count', 0)}`
                - **📝 Số bản ghi lịch sử Logs:** `{stats.get('log_count', 0)}`
                - **🎯 Số mốc chuẩn Baseline:** `{stats.get('baseline_count', 0)}`
                - **💾 Dung lượng file:** `{stats.get('size_kb', 0)} KB`
                """)

                st.info("ℹ️ **Cơ chế an toàn:** Hệ thống sẽ **tự động sao lưu một bản dự phòng (Safety Auto-Backup)** của CSDL hiện tại trước khi thực hiện ghi đè, đảm bảo tuyệt đối không mất mát dữ liệu.")

                if st.button("⚠️ Xác nhận Khôi phục Cơ sở Dữ liệu Ngay", type="primary", use_container_width=True):
                    with st.spinner("Đang tiến hành sao lưu an toàn và ghi đè CSDL..."):
                        restore_ok, restore_msg = restore_db_from_bytes(db_bytes)
                        if restore_ok:
                            st.success(f"🎉 {restore_msg}")
                            st.toast("Khôi phục CSDL thành công!", icon="✅")
                            st.rerun()
                        else:
                            st.error(f"❌ {restore_msg}")
            else:
                st.error(f"❌ {inspect_msg}")

if __name__ == "__main__":
    render_configuration_page()


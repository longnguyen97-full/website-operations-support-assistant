import streamlit as st
import pandas as pd
from datetime import datetime

import config
from database import (
    init_db,
    get_system_settings,
    update_system_settings
)
from notifications.email_service import (
    send_test_email,
    send_periodic_report_email
)
from scheduler import update_scheduler_interval

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
    st.markdown("Quản lý toàn bộ tham số cấu hình động vận hành hệ thống lưu trữ trực tiếp trong CSDL SQLite (`monitoring.db`).")

    with st.expander("ℹ️ Hướng dẫn lấy Mật khẩu ứng dụng (App Password) cho Gmail"):
        st.markdown("""
        1. Bật **Xác thực 2 bước (2-Step Verification)** trên tài khoản Google.
        2. Truy cập: [Google App Passwords](https://myaccount.google.com/apppasswords).
        3. Tạo mật khẩu ứng dụng mới với tên `Website Monitor`.
        4. Sao chép chuỗi mật khẩu 16 ký tự vào ô **Mật khẩu ứng dụng (App Password)** bên dưới.
        """)

    with st.form("dynamic_system_config_form"):
        # 1. Cấu hình Email & SMTP
        st.markdown("### 1. 📧 Dịch vụ Email & Máy chủ SMTP")
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

        # 2. Báo cáo Sức khỏe Định kỳ
        st.markdown("---")
        st.markdown("### 2. 📊 Báo cáo Sức khỏe Định kỳ Hàng ngày (Daily Health Digest)")
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

        # 3. Cảnh báo Sự cố tức thời
        st.markdown("---")
        st.markdown("### 3. 🚨 Quy tắc Cảnh báo Sự cố Tức thời (Incident Alerts)")
        c8, c9, c10 = st.columns(3)
        notify_critical = c8.checkbox("🚨 Gửi khi có lỗi CRITICAL (Website Down, SSL Expired, DNS Failed)", value=bool(settings.get("notify_on_critical", 1)))
        notify_warning = c9.checkbox("⚠️ Gửi khi có cảnh báo WARNING (SSL sắp hết hạn)", value=bool(settings.get("notify_on_warning", 1)))
        notify_recovery = c10.checkbox("✅ Gửi khi dịch vụ PHỤC HỒI (Recovery)", value=bool(settings.get("notify_on_recovery", 1)))

        cooldown = st.number_input(
            "Thời gian chờ giữa các lần gửi cảnh báo lặp lại (Cooldown phút):", 
            min_value=1, max_value=1440, 
            value=int(settings.get("cooldown_minutes", config.DEFAULT_COOLDOWN_MINUTES))
        )

        # 4. Tham số Lập lịch & Lưu trữ
        st.markdown("---")
        st.markdown("### 4. ⏱️ Tham số Bộ lập lịch (Scheduler) & Vận hành")
        c11, c12, c13 = st.columns(3)
        sched_interval = c11.number_input(
            "Chu kỳ quét định kỳ mặc định (giây):", 
            min_value=10, max_value=3600, 
            value=int(settings.get("scheduler_interval_seconds", config.DEFAULT_SCHEDULER_INTERVAL_SECONDS))
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
                "scheduler_interval_seconds": sched_interval,
                "data_retention_days": retention_days,
                "ssl_warning_days": ssl_warn_days
            }
            update_system_settings(updated_data)
            update_scheduler_interval(int(sched_interval))
            st.success("✅ Đã cập nhật và lưu cấu hình động thành công vào Database!")
            st.toast("Đã lưu cấu hình thành công!", icon="💾")

    # Thao tác gửi email & test
    st.markdown("---")
    st.markdown("### 5. 🚀 Thao tác Kiểm thử Nhanh")
    col_act1, col_act2 = st.columns(2)
    if col_act1.button("📊 Gửi Báo Cáo Định Kỳ 24h Ngay Lập Tức", type="primary", use_container_width=True):
        current_cfg = get_system_settings()
        with st.spinner("Đang tổng hợp dữ liệu 24h qua và gửi email báo cáo..."):
            success, msg = send_periodic_report_email(hours=24, settings=current_cfg)
            if success:
                st.success("🎉 " + msg)
            else:
                st.error("❌ " + msg)

    if col_act2.button("🧪 Gửi Email Thử Nghiệm Kết Nối SMTP", use_container_width=True):
        current_cfg = get_system_settings()
        with st.spinner("Đang kết nối tới máy chủ SMTP và gửi email thử nghiệm..."):
            success, msg = send_test_email(current_cfg)
            if success:
                st.success("🎉 " + msg)
            else:
                st.error("❌ " + msg)

if __name__ == "__main__":
    render_configuration_page()

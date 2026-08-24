import streamlit as st
from tools.http_checker import check_http
from tools.dns_checker import check_dns
from tools.ssl_checker import check_ssl
from tools.visual_checker import check_visual_regression, capture_screenshot
from ui import render_dashboard
from database import (
    init_db,
    get_all_websites,
    get_active_baseline,
    save_monitoring_log,
    calculate_overall_status,
    add_or_update_website,
    get_system_settings
)
from notifications import check_and_send_alert
from scheduler import (
    start_background_scheduler,
    stop_background_scheduler,
    update_scheduler_interval,
    run_monitors_now,
    get_scheduler_info
)
from scheduler.monitor_scheduler import resume_background_scheduler

from config import DEFAULT_SCHEDULER_INTERVAL_SECONDS, HTTP_TIMEOUT_SECONDS, DNS_TIMEOUT_SECONDS, SSL_TIMEOUT_SECONDS

# --- Cấu hình trang ---
st.set_page_config(layout="wide", page_title="Agentic AI Monitoring Dashboard", page_icon="🛡️")

@st.cache_resource
def setup_background_monitoring():
    """Khởi chạy Background Scheduler 1 lần duy nhất trong vòng đời ứng dụng."""
    init_db()
    start_background_scheduler(interval_seconds=DEFAULT_SCHEDULER_INTERVAL_SECONDS)
    return True

def main():
    # 1. Khởi tạo CSDL SQLite & APScheduler
    init_db()
    setup_background_monitoring()
    
    st.title("🛡️ Agentic AI Monitoring Dashboard")
    
    # 2. Lấy danh sách website từ CSDL
    websites = get_all_websites()
    if not websites:
        st.warning("⚠️ Chưa có website nào trong hệ thống CSDL. Vui lòng thêm website ở thanh bên trái.")
        site_names = []
    else:
        site_names = [w["name"] for w in websites]

    # 3. Sidebar: Quản lý & Kích hoạt Giám sát
    st.sidebar.header("🎯 Mục tiêu Giám sát")
    if site_names:
        selected_name = st.sidebar.selectbox("Chọn Website cần kiểm tra:", site_names)
        selected_site = next(w for w in websites if w["name"] == selected_name)
        
        # NÚT KIỂM TRA THỦ CÔNG NẰM NGAY DƯỚI DROPDOWN LIST
        run_check_clicked = st.sidebar.button(
            "🚀 Kiểm tra thủ công website này", 
            use_container_width=True, 
            type="primary"
        )

        enable_screenshot = st.sidebar.checkbox(
            "📸 Kèm chụp ảnh Playwright khi quét", 
            value=True,
            help="Tự động sử dụng Playwright mở trình duyệt headless và chụp ảnh giao diện để so sánh Visual Regression"
        )

        quick_shot_clicked = st.sidebar.button(
            "📸 Chỉ chụp ảnh màn hình (Screenshot)",
            use_container_width=True
        )

        # Thông tin tóm tắt nhanh website
        st.sidebar.markdown("---")
        st.sidebar.markdown(f"**🌐 URL:** `{selected_site['url']}`")
        st.sidebar.markdown(f"**🏷️ Domain:** `{selected_site['domain']}`")
        st.sidebar.markdown(f"**🎯 Mã HTTP kỳ vọng:** `{selected_site['expected_status']}`")
        
        active_b = get_active_baseline(selected_site["id"])
        if active_b:
            st.sidebar.caption(f"📌 **Baseline đang active:** {active_b.get('note', 'N/A')}")
    else:
        st.sidebar.warning("⚠️ Chưa có website nào trong hệ thống CSDL.")
        st.sidebar.info("👉 Vui lòng cấu hình thêm website tại trang `/configuration`.")
        selected_site = None
        run_check_clicked = False
        enable_screenshot = False
        quick_shot_clicked = False

    # 4. Trạng thái session state cho kết quả quét
    if "last_scan" not in st.session_state:
        st.session_state["last_scan"] = {}

    # Xử lý nút Chỉ chụp ảnh màn hình
    if selected_site and quick_shot_clicked:
        with st.spinner(f"Đang sử dụng Playwright chụp ảnh màn hình '{selected_site['name']}'..."):
            visual_res = check_visual_regression(
                url=selected_site["url"],
                website_identifier=selected_site["name"],
                timeout=20.0
            )
            if selected_site["id"] not in st.session_state["last_scan"]:
                st.session_state["last_scan"][selected_site["id"]] = {}
            st.session_state["last_scan"][selected_site["id"]]["visual"] = visual_res
            st.toast("Đã chụp ảnh màn hình với Playwright thành công!", icon="📸")

    # Xử lý nút Kiểm tra thủ công đầy đủ
    if selected_site and run_check_clicked:
        # Lấy active baseline từ DB nếu có
        active_baseline_record = get_active_baseline(selected_site["id"])
        baseline_dns = active_baseline_record.get("baseline_dns") if active_baseline_record else None
        expected_status = (
            active_baseline_record.get("expected_http_status") 
            if active_baseline_record and active_baseline_record.get("expected_http_status") 
            else selected_site.get("expected_status", 200)
        )

        # Lấy cấu hình timeout động từ hệ thống
        sys_settings = get_system_settings()
        http_timeout = float(sys_settings.get("http_timeout_seconds") or HTTP_TIMEOUT_SECONDS)
        dns_timeout = float(sys_settings.get("dns_timeout_seconds") or DNS_TIMEOUT_SECONDS)
        ssl_timeout = float(sys_settings.get("ssl_timeout_seconds") or SSL_TIMEOUT_SECONDS)

        with st.spinner(f"Đang chạy các công cụ giám sát cho '{selected_site['name']}'..."):
            # 1. Gọi các Tools với timeout động
            http_res = check_http(selected_site["url"], expected_status=expected_status, timeout=http_timeout)
            dns_res = check_dns(selected_site["domain"], baseline=baseline_dns, timeout=dns_timeout)
            ssl_res = check_ssl(selected_site["url"], timeout=ssl_timeout)
            
            visual_res = None
            if enable_screenshot:
                try:
                    visual_res = check_visual_regression(
                        url=selected_site["url"],
                        website_identifier=selected_site["name"],
                        timeout=20.0
                    )
                except Exception as ex:
                    visual_res = {"error": str(ex), "status": "ERROR"}

            # 2. Lưu kết quả vào CSDL SQLite (monitoring_logs)
            save_monitoring_log(
                website_id=selected_site["id"],
                website_name=selected_site["name"],
                http_res=http_res,
                dns_res=dns_res,
                ssl_res=ssl_res
            )
            
            # 3. Kích hoạt cảnh báo Email nếu có sự cố
            overall_status = calculate_overall_status(http_res, dns_res, ssl_res)
            try:
                check_and_send_alert(selected_site, overall_status, http_res, dns_res, ssl_res)
            except Exception:
                pass

            # Lưu vào session để duy trì hiển thị
            st.session_state["last_scan"][selected_site["id"]] = {
                "http": http_res,
                "dns": dns_res,
                "ssl": ssl_res,
                "visual": visual_res
            }
            st.toast(f"Đã hoàn thành kiểm tra và chụp ảnh Playwright!", icon="✅")

    # 5. Hiển thị Dashboard
    if selected_site:
        current_site_scan = st.session_state["last_scan"].get(selected_site["id"])
        if current_site_scan and current_site_scan.get("http"):
            render_dashboard(
                selected_site=selected_site,
                http_res=current_site_scan.get("http"),
                dns_res=current_site_scan.get("dns"),
                ssl_res=current_site_scan.get("ssl"),
                visual_res=current_site_scan.get("visual")
            )
        else:
            render_dashboard(
                selected_site=selected_site,
                visual_res=current_site_scan.get("visual") if current_site_scan else None
            )

if __name__ == "__main__":
    main()
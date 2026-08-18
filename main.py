import streamlit as st
from tools.http_checker import check_http
from tools.dns_checker import check_dns
from tools.ssl_checker import check_ssl
from ui import render_dashboard
from database import (
    init_db,
    get_all_websites,
    get_active_baseline,
    save_monitoring_log,
    calculate_overall_status,
    add_or_update_website
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

from config import DEFAULT_SCHEDULER_INTERVAL_SECONDS

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

    # 3. Sidebar: Quản lý Website
    st.sidebar.header("⚙️ Quản lý Giám sát")
    if site_names:
        selected_name = st.sidebar.selectbox("Chọn Website:", site_names)
        selected_site = next(w for w in websites if w["name"] == selected_name)
    else:
        selected_site = None

    # Form thêm website mới
    with st.sidebar.expander("➕ Thêm Website Giám sát Mới"):
        with st.form("add_site_form"):
            new_name = st.text_input("Tên Website:", placeholder="Google")
            new_url = st.text_input("URL:", placeholder="https://www.google.com")
            new_domain = st.text_input("Domain:", placeholder="google.com")
            new_exp_status = st.number_input("Mã HTTP kỳ vọng:", min_value=100, max_value=599, value=200)
            submitted = st.form_submit_button("Thêm vào CSDL")
            if submitted and new_name and new_url and new_domain:
                add_or_update_website(new_name, new_url, new_domain, int(new_exp_status))
                st.success(f"Đã thêm '{new_name}' vào CSDL thành công!")
                st.rerun()

    # 4. Sidebar: Điều khiển APScheduler
    st.sidebar.markdown("---")
    st.sidebar.header("⏱️ Background Scheduler (APScheduler)")
    sched_info = get_scheduler_info()
    
    status_badge = "🟢 Đang Chạy Tự Động" if sched_info["is_running"] else "🔴 Đang Tạm Dừng"
    st.sidebar.markdown(f"**Trạng thái:** {status_badge}")
    if sched_info.get("next_run_time"):
        st.sidebar.caption(f"🕒 Lần quét kế (UTC+7): `{sched_info['next_run_time']}`")
    if sched_info.get("last_run_time"):
        last_t = str(sched_info['last_run_time']).replace('T', ' ')[:19]
        st.sidebar.caption(f"✅ Lần quét trước: `{last_t}` ({sched_info['total_runs']} lần quét)")

    # Tần suất quét
    new_interval = st.sidebar.select_slider(
        "Tần suất quét định kỳ:",
        options=[30, 60, 120, 300, 600],
        value=sched_info["interval_seconds"],
        format_func=lambda x: f"{x} giây" if x < 60 else f"{x//60} phút"
    )
    if new_interval != sched_info["interval_seconds"]:
        update_scheduler_interval(new_interval)
        st.sidebar.success(f"Đã đổi chu kỳ quét thành {new_interval}s!")

    col_btn1, col_btn2 = st.sidebar.columns(2)
    if sched_info["is_running"]:
        if col_btn1.button("⏸️ Tạm dừng", use_container_width=True):
            stop_background_scheduler()
            st.rerun()
    else:
        if col_btn1.button("▶️ Tiếp tục", use_container_width=True):
            resume_background_scheduler()
            st.rerun()

    if col_btn2.button("⚡ Quét ngay tất cả", use_container_width=True):
        with st.spinner("Đang chạy quét định kỳ toàn bộ website..."):
            run_monitors_now()
            st.toast("Đã hoàn tất quét tất cả website và lưu CSDL!", icon="⚡")
            st.rerun()

    # 5. Execution logic & Dashboard Rendering
    if selected_site:
        # Lấy active baseline từ DB nếu có
        active_baseline_record = get_active_baseline(selected_site["id"])
        baseline_dns = active_baseline_record.get("baseline_dns") if active_baseline_record else None
        expected_status = (
            active_baseline_record.get("expected_http_status") 
            if active_baseline_record and active_baseline_record.get("expected_http_status") 
            else selected_site.get("expected_status", 200)
        )

        # Trạng thái session state cho kết quả quét
        if "last_scan" not in st.session_state:
            st.session_state["last_scan"] = {}

        if st.sidebar.button("🚀 Kiểm tra thủ công website này", use_container_width=True, type="primary"):
            with st.spinner(f"Đang chạy các công cụ giám sát cho '{selected_site['name']}'..."):
                # 1. Gọi các Tools
                http_res = check_http(selected_site["url"], expected_status=expected_status)
                dns_res = check_dns(selected_site["domain"], baseline=baseline_dns)
                ssl_res = check_ssl(selected_site["url"])
                
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
                    "ssl": ssl_res
                }
                st.toast(f"Đã hoàn thành kiểm tra và lưu lịch sử vào CSDL!", icon="✅")

        # Hiển thị Dashboard
        current_site_scan = st.session_state["last_scan"].get(selected_site["id"])
        if current_site_scan:
            render_dashboard(
                selected_site=selected_site,
                http_res=current_site_scan["http"],
                dns_res=current_site_scan["dns"],
                ssl_res=current_site_scan["ssl"]
            )
        else:
            render_dashboard(selected_site=selected_site)

if __name__ == "__main__":
    main()
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
    add_or_update_website
)

# --- Cấu hình trang ---
st.set_page_config(layout="wide", page_title="Agentic AI Monitoring Dashboard", page_icon="🛡️")

def main():
    # 1. Khởi tạo CSDL SQLite (tự động tạo tables và seed dữ liệu ban đầu nếu trống)
    init_db()
    
    st.title("🛡️ Agentic AI Monitoring Dashboard")
    
    # 2. Lấy danh sách website từ CSDL
    websites = get_all_websites()
    if not websites:
        st.warning("⚠️ Chưa có website nào trong hệ thống CSDL. Vui lòng thêm website ở thanh bên trái.")
        site_names = []
    else:
        site_names = [w["name"] for w in websites]

    # 3. Sidebar selection & Thêm website mới
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

    # 4. Execution logic & Dashboard Rendering
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

        if st.sidebar.button("🚀 Kiểm tra ngay", use_container_width=True, type="primary"):
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
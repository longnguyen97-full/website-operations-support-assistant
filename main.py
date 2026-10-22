import streamlit as st
from ui import render_dashboard
from database import (
    init_db,
    get_all_websites,
    get_active_baseline
)
from scheduler import start_background_scheduler
from config import DEFAULT_SCHEDULER_INTERVAL_SECONDS

# --- Cấu hình trang ---
st.set_page_config(layout="wide", page_title="SRE Agentic System - Enterprise Website Operations Platform", page_icon="🛡️")

@st.cache_resource
def setup_background_monitoring():
    """Khởi chạy Background Scheduler 1 lần duy nhất trong vòng đời ứng dụng."""
    init_db()
    from database import get_system_settings
    sys_settings = get_system_settings()
    interval = int(sys_settings.get("scheduler_interval_seconds") or DEFAULT_SCHEDULER_INTERVAL_SECONDS)
    start_background_scheduler(interval_seconds=interval)
    return True

def main():
    # 1. Khởi tạo CSDL SQLite & APScheduler
    init_db()
    setup_background_monitoring()
    
    st.title("🛡️ SRE Agentic System - Enterprise Website Operations Platform")
    
    # 2. Lấy danh sách website từ CSDL
    websites = get_all_websites()
    if not websites:
        st.warning("⚠️ Chưa có website nào trong hệ thống CSDL. Vui lòng thêm website tại trang `/configuration`.")
        site_names = []
    else:
        site_names = [w["name"] for w in websites]

    # 3. Sidebar: Quản lý Mục tiêu Giám sát (Đã làm gọn, loại bỏ các nút chế độ ở sidebar)
    st.sidebar.header("🎯 Mục tiêu Giám sát")
    if site_names:
        # Tra cứu nhanh danh sách site_id có active baseline
        site_map = {w["name"]: w for w in websites}
        
        def format_site_label(name):
            site_obj = site_map.get(name)
            if site_obj:
                b = get_active_baseline(site_obj["id"])
                tag = "🏷️ Baseline" if b else "⚪ No Baseline"
                return f"[{tag}] {name}"
            return name

        selected_name = st.sidebar.selectbox("Chọn Website cần kiểm tra:", site_names, format_func=format_site_label)
        selected_site = site_map[selected_name]

        # Thông tin tóm tắt nhanh website
        st.sidebar.markdown("---")
        st.sidebar.markdown(f"**🌐 URL:** `{selected_site['url']}`")
        st.sidebar.markdown(f"**🏷️ Domain:** `{selected_site['domain']}`")
        st.sidebar.markdown(f"**🎯 Mã HTTP kỳ vọng:** `{selected_site['expected_status']}`")
        
        active_b = get_active_baseline(selected_site["id"])
        if active_b:
            st.sidebar.success(f"🏷️ **Baseline:** Đang kích hoạt (#{active_b['id']})")
        else:
            st.sidebar.warning("⚪ **Baseline:** Chưa có (Cold-start / Unmanaged)")
        
        st.sidebar.markdown("---")
        st.sidebar.info("💡 **Ghi chú:** Chọn website mục tiêu và chuyển đổi giữa các Tab để xem Telemetry hoặc kích hoạt Tác tử SRE.")
    else:
        st.sidebar.warning("⚠️ Chưa có website nào trong hệ thống CSDL.")
        st.sidebar.info("👉 Vui lòng cấu hình thêm website tại trang `/configuration`.")
        selected_site = None

    # 4. Trạng thái session state cho kết quả quét
    if "last_scan" not in st.session_state:
        st.session_state["last_scan"] = {}
    if "last_agent_result" not in st.session_state:
        st.session_state["last_agent_result"] = None

    # 5. Hiển thị Dashboard Vận hành Production
    if selected_site:
        render_dashboard(selected_site=selected_site)

if __name__ == "__main__":
    main()
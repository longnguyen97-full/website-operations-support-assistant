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
        st.warning("⚠️ Chưa có website nào trong hệ thống CSDL. Vui lòng thêm website tại trang `/configuration`.")
        site_names = []
    else:
        site_names = [w["name"] for w in websites]

    # 3. Sidebar: Quản lý Mục tiêu Giám sát (Đã làm gọn, loại bỏ các nút chế độ ở sidebar)
    st.sidebar.header("🎯 Mục tiêu Giám sát")
    if site_names:
        selected_name = st.sidebar.selectbox("Chọn Website cần kiểm tra:", site_names)
        selected_site = next(w for w in websites if w["name"] == selected_name)

        # Thông tin tóm tắt nhanh website
        st.sidebar.markdown("---")
        st.sidebar.markdown(f"**🌐 URL:** `{selected_site['url']}`")
        st.sidebar.markdown(f"**🏷️ Domain:** `{selected_site['domain']}`")
        st.sidebar.markdown(f"**🎯 Mã HTTP kỳ vọng:** `{selected_site['expected_status']}`")
        
        active_b = get_active_baseline(selected_site["id"])
        if active_b:
            st.sidebar.caption(f"📌 **Baseline đang active:** {active_b.get('note', 'N/A')}")
        
        st.sidebar.markdown("---")
        st.sidebar.info("💡 **Ghi chú:** Mỗi Cấu hình Giám sát có nút thực thi độc lập bên trong từng Tab tương ứng.")
    else:
        st.sidebar.warning("⚠️ Chưa có website nào trong hệ thống CSDL.")
        st.sidebar.info("👉 Vui lòng cấu hình thêm website tại trang `/configuration`.")
        selected_site = None

    # 4. Trạng thái session state cho kết quả quét từng cấu hình
    if "last_trad_scan" not in st.session_state:
        st.session_state["last_trad_scan"] = {}
    if "last_scan" not in st.session_state:
        st.session_state["last_scan"] = {}
    if "last_agent_result" not in st.session_state:
        st.session_state["last_agent_result"] = None

    # 5. Hiển thị Dashboard phân tách rạch ròi 6 Tabs
    if selected_site:
        render_dashboard(selected_site=selected_site)

if __name__ == "__main__":
    main()
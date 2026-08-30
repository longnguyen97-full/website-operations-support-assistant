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
        
        # BỘ ĐIỀU KHIỂN 3 CHẾ ĐỘ GIÁM SÁT & ĐỐI CHỨNG
        st.sidebar.markdown("### 🎛️ Chọn Chế Độ Giám Sát Cần Chạy:")
        
        # 1. Chế độ Bán tự động (Đa tín hiệu + Z-Score)
        btn_mode2_semi = st.sidebar.button(
            "🛡️ Chạy Giám Sát Bán Tự Động",
            help="Cơ chế 'Suggest & Approve': Thu thập đa tín hiệu (HTTP, DNS, SSL, Visual), so khớp luật RFC và thống kê Z-Score để lọc nhiễu cảnh báo.",
            use_container_width=True,
            type="primary"
        )

        # 2. Chế độ Tự động Agentic AI (Multi-Agent)
        btn_mode3_agentic = st.sidebar.button(
            "🧠 Chạy Giám Sát Agentic AI Tự Động",
            help="Cơ chế 'Autonomous Reasoning': Hệ thống 6 Tác tử tự hành (Planning -> Tool-use -> Self-correction -> LLM RCA 8 phần).",
            use_container_width=True
        )

        # 3. Chế độ Truyền thống (Ngưỡng cứng)
        btn_mode1_trad = st.sidebar.button(
            "⚠️ Chạy Giám Sát Truyền Thống",
            help="Cơ chế 'Detect & Alert': Chỉ kiểm tra mã HTTP và ngưỡng thời gian phản hồi cố định.",
            use_container_width=True
        )

        # 4. Chạy Đối chứng Cả 3 Chế độ
        btn_mode4_benchmark = st.sidebar.button(
            "⚖️ Chạy Đối Chứng Song Song Cả 3 Chế Độ",
            help="Kích hoạt đồng thời cả 3 thế hệ giám sát trên cùng 1 phiên quét để so sánh hiệu năng và độ chính xác.",
            use_container_width=True
        )

        enable_screenshot = st.sidebar.checkbox(
            "📸 Kèm chụp ảnh Playwright khi quét", 
            value=True,
            help="Tự động sử dụng Playwright mở trình duyệt headless và chụp ảnh giao diện để so sánh Visual Regression"
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
        btn_mode1_trad = False
        btn_mode2_semi = False
        btn_mode3_agentic = False
        btn_mode4_benchmark = False
        enable_screenshot = False

    # 4. Trạng thái session state cho kết quả quét
    if "last_scan" not in st.session_state:
        st.session_state["last_scan"] = {}
    if "last_agent_result" not in st.session_state:
        st.session_state["last_agent_result"] = None
    if "active_mode_label" not in st.session_state:
        st.session_state["active_mode_label"] = "Chưa kích hoạt phiên quét"

    # Xử lý Nút Chạy Tác tử Agentic AI (Mode 3) hoặc Đối chứng (Mode 4)
    if selected_site and (btn_mode3_agentic or btn_mode4_benchmark):
        from agents.orchestrator import MonitoringOrchestratorAgent
        from database.repository import get_website_latency_history
        mode_text = "Chế độ 3: Giám sát Agentic AI Tự động" if btn_mode3_agentic else "Chế độ 4: Đối chứng Toàn diện 3 Cấu hình"
        st.session_state["active_mode_label"] = mode_text
        with st.spinner(f"🤖 Đang điều động chu trình Agentic AI điều tra '{selected_site['name']}'..."):
            orchestrator = MonitoringOrchestratorAgent()
            active_baseline_record = get_active_baseline(selected_site["id"])
            hist_lat = get_website_latency_history(selected_site["id"], limit=15)
            agent_res = orchestrator.run_agentic_workflow(
                website_info=selected_site,
                active_baseline=active_baseline_record,
                history_latencies=hist_lat,
                enable_visual=enable_screenshot
            )
            st.session_state["last_agent_result"] = agent_res

            # Đồng bộ kết quả probes vào last_scan
            ev = agent_res.get("evidence", {})
            st.session_state["last_scan"][selected_site["id"]] = {
                "http": ev.get("http"),
                "dns": ev.get("dns"),
                "ssl": ev.get("ssl"),
                "visual": ev.get("visual")
            }
            # Lưu monitoring log
            if ev.get("http") and ev.get("dns") and ev.get("ssl"):
                save_monitoring_log(
                    website_id=selected_site["id"],
                    website_name=selected_site["name"],
                    http_res=ev.get("http"),
                    dns_res=ev.get("dns"),
                    ssl_res=ev.get("ssl")
                )
            st.toast(f"Tác tử Agentic AI đã hoàn tất điều tra & sinh báo cáo RCA!", icon="🧠")

    # Xử lý Nút Chạy Giám sát Bán tự động (Mode 2) hoặc Truyền thống (Mode 1)
    elif selected_site and (btn_mode2_semi or btn_mode1_trad):
        mode_text = "Chế độ 2: Giám sát Bán tự động (Đa tín hiệu + Z-Score)" if btn_mode2_semi else "Chế độ 1: Giám sát Truyền thống (Ngưỡng cứng)"
        st.session_state["active_mode_label"] = mode_text

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
        current_agent_res = st.session_state.get("last_agent_result")
        if current_agent_res and current_agent_res.get("website_name") != selected_site["name"]:
            current_agent_res = None

        if current_site_scan and current_site_scan.get("http"):
            render_dashboard(
                selected_site=selected_site,
                http_res=current_site_scan.get("http"),
                dns_res=current_site_scan.get("dns"),
                ssl_res=current_site_scan.get("ssl"),
                visual_res=current_site_scan.get("visual"),
                agent_result=current_agent_res
            )
        else:
            render_dashboard(
                selected_site=selected_site,
                visual_res=current_site_scan.get("visual") if current_site_scan else None,
                agent_result=current_agent_res
            )

if __name__ == "__main__":
    main()
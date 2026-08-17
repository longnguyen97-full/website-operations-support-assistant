import streamlit as st
import pandas as pd
from datetime import datetime
from database.repository import (
    save_milestone_baseline,
    get_monitoring_logs,
    get_all_milestones,
    set_active_milestone,
    get_active_baseline
)

def render_realtime_tab(selected_site, http_res, dns_res, ssl_res):
    """Hiển thị kết quả kiểm tra thời gian thực và cho phép lưu Mốc chuẩn."""
    st.subheader(f"📊 Kết quả kiểm tra: {selected_site['name']}")
    
    # 1. HTTP Section (RFC 9110)
    st.markdown("### 🌐 HTTP Monitoring (RFC 9110)")
    cols = st.columns(4)
    status_label = f"{http_res.get('status_code')} ({http_res.get('status_category', 'N/A')})" if http_res.get('status_code') else "N/A"
    cols[0].metric("Status", status_label)
    cols[1].metric("Latency", f"{http_res.get('response_time_ms')} ms")
    cols[2].metric("Method", http_res.get("method"))
    cols[3].metric("Result", "Match Expected" if http_res.get("is_expected_status") else "Status Mismatch")
    
    if http_res.get("redirect_chain"):
        st.info(f"🔄 **Redirect Chain:** " + " ➔ ".join([f"`{hop['url']} ({hop['status_code']})`" for hop in http_res["redirect_chain"]]))
    
    if http_res.get("headers"):
        with st.expander("🔍 HTTP Headers (Caching & Server)"):
            st.json(http_res["headers"])
            
    if http_res.get("error"):
        st.error(f"❌ HTTP Error [{http_res.get('error_type')}]: {http_res.get('error')}")

    st.markdown("---")

    # 2. DNS Section (RFC 1035)
    st.markdown("### 🗂️ DNS Monitoring (RFC 1035)")
    if dns_res.get("resolved"):
        st.success(f"✅ DNS Resolution: Success ({dns_res.get('resolution_time_ms')} ms)")
        
        table_data = {
            "Record Type": ["A (IPv4)", "AAAA (IPv6)", "CNAME", "MX", "TXT"],
            "Values": [
                ", ".join(dns_res.get("a", [])) or "None",
                ", ".join(dns_res.get("aaaa", [])) or "None",
                str(dns_res.get("cname")) or "None",
                "; ".join(dns_res.get("mx", [])) or "None",
                "; ".join(dns_res.get("txt", [])) or "None"
            ],
            "TTL (s)": [
                str(dns_res.get("ttl", {}).get("a", "-")),
                str(dns_res.get("ttl", {}).get("aaaa", "-")),
                str(dns_res.get("ttl", {}).get("cname", "-")),
                str(dns_res.get("ttl", {}).get("mx", "-")),
                str(dns_res.get("ttl", {}).get("txt", "-"))
            ]
        }
        st.table(table_data)
        
        if dns_res.get("is_load_balancing_suspected"):
            st.info("ℹ️ **Cơ chế Load Balancing / CDN:** Phát hiện nhiều địa chỉ IP hoặc phân phối vòng tròn (Round-Robin).")
            
        if dns_res.get("changes_detected"):
            with st.expander("⚠️ Chi tiết thay đổi so với DNS Baseline"):
                st.json(dns_res["changes_detected"])
    else:
        st.error(f"❌ DNS Resolution: Failed - {dns_res.get('error')}")

    st.markdown("---")

    # 3. SSL/TLS Section (RFC 5280 & RFC 8446)
    st.markdown("### 🔒 SSL/TLS Monitoring (RFC 5280 & RFC 8446)")
    if ssl_res.get("is_valid"):
        st.success("✅ Certificate Status: Valid & Trusted")
    else:
        st.error(f"❌ Certificate Status: Invalid / Issue Detected ({ssl_res.get('error_type') or 'Untrusted'})")

    cols = st.columns(4)
    cols[0].metric("Days Remaining", ssl_res.get("days_remaining"))
    cols[1].metric("TLS Version", ssl_res.get("tls_version") or "N/A")
    cols[2].metric("Hostname Match", "Matched" if ssl_res.get("hostname_matched") else "Mismatch")
    cols[3].metric("Issuer", ssl_res.get("issuer") or "N/A")

    if ssl_res.get("error"):
        st.warning(f"⚠️ Chi tiết lỗi SSL: `{ssl_res.get('error')}`")
        
    with st.expander("📜 Chi tiết Chứng chỉ X.509"):
        st.json({
            "Hostname": ssl_res.get("hostname"),
            "Issuer": ssl_res.get("issuer"),
            "Subject CN": ssl_res.get("subject_common_name"),
            "SANs": ssl_res.get("subject_alternative_names"),
            "Valid From": ssl_res.get("not_before"),
            "Valid To": ssl_res.get("not_after"),
            "Is Self Signed": ssl_res.get("is_self_signed"),
            "Is Expired": ssl_res.get("is_expired"),
            "Is Untrusted CA": ssl_res.get("is_untrusted_ca")
        })

    # 4. Action: Lưu làm Mốc chuẩn (Milestone)
    st.markdown("---")
    st.markdown("### 📌 Thiết lập Mốc chuẩn (Milestone Baseline)")
    with st.form("save_milestone_form"):
        note = st.text_input("Ghi chú mốc chuẩn:", placeholder="Ví dụ: Cấu hình chuẩn trước đợt bảo trì hệ thống...")
        set_active = st.checkbox("Kích hoạt mốc này làm Baseline mặc định (is_active)", value=True)
        submitted = st.form_submit_button("💾 Lưu làm Mốc chuẩn mới")
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
    chart_df["timestamp"] = pd.to_datetime(chart_df["timestamp"])
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
    display_df.columns = [
        "Thời điểm (UTC)", "Trạng thái", "Mã HTTP", 
        "Độ trễ HTTP (ms)", "DNS Resolved", "SSL Hợp lệ", "SSL Ngày còn lại"
    ]
    st.dataframe(display_df, use_container_width=True)

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
                    st.success(f"Đã kích hoạt mốc #{m['id']} thành công!")
                    st.rerun()

def render_dashboard(selected_site, http_res=None, dns_res=None, ssl_res=None):
    """Giao diện Dashboard phân chia theo 3 Tabs chuyên biệt."""
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
import streamlit as st
import json
from tools.http_checker import check_http
from tools.dns_checker import check_dns
from tools.ssl_checker import check_ssl
from ui import render_dashboard

# --- Cấu hình trang ---
st.set_page_config(layout="wide")

def main():
    # 1. Load config
    with open("target_websites.json", "r") as f:
        config = json.load(f)
        
    st.title("🛡️ Agentic AI Monitoring Dashboard")
    
    # 2. Sidebar selection
    site_names = [w["name"] for w in config["websites"]]
    selected_name = st.sidebar.selectbox("Chọn Website:", site_names)
    selected_site = next(w for w in config["websites"] if w["name"] == selected_name)

    # 3. Execution logic
    if st.sidebar.button("Kiểm tra ngay"):
        with st.spinner("Đang chạy công cụ giám sát..."):
            # Gọi tools
            expected_st = selected_site.get("expected_status", 200)
            http_res = check_http(selected_site["url"], expected_status=expected_st)
            dns_res = check_dns(selected_site["domain"], selected_site.get("baseline_dns"))
            ssl_res = check_ssl(selected_site["url"])
            
            # Gọi UI để render kết quả
            render_dashboard(selected_site, http_res, dns_res, ssl_res)

if __name__ == "__main__":
    main()
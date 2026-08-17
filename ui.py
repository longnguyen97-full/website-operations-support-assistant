import streamlit as st

def render_dashboard(selected_site, http_res, dns_res, ssl_res):
    st.subheader(f"📊 Giám sát: {selected_site['name']}")
    
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
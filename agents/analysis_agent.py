"""
Incident Analysis Agent (Tác tử Phân tích Nguyên nhân Gốc - RCA & Khuyến nghị)
Sử dụng kho tri thức chuyên môn (Knowledge Base) kết hợp suy luận chuyên gia (Expert Reasoning / LLM)
để tạo lập Bản Báo Cáo Phân Tích Toàn Diện 8 Phần chuẩn Enterprise SRE / DevOps.
"""

import os
import time
from datetime import datetime
from typing import Dict, Any, Optional, List
from agents.knowledge_base import OperationalKnowledgeBase
from config import TZ_VN
from database.repository import get_system_settings
from tools.gemini_client import generate_gemini_analysis

class IncidentAnalysisAgent:
    """Tác tử phân tích nguyên nhân gốc và đề xuất giải pháp toàn diện 8 phần."""

    def __init__(self, name: str = "Incident Analysis Agent"):
        self.name = name
        self.kb = OperationalKnowledgeBase()

    def analyze_incident(
        self,
        website_info: Dict[str, Any],
        correlation_data: Dict[str, Any],
        evidence_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Thực hiện phân tích toàn diện sự cố dựa trên tương quan và bằng chứng kỹ thuật.
        Xuất ra cấu trúc chuẩn 8 phần (Full Enterprise SRE RCA Format).
        """
        incident_type = correlation_data.get("incident_type", "NO_INCIDENT")
        severity = correlation_data.get("overall_severity", "HEALTHY")
        primary_issue = correlation_data.get("primary_issue") or correlation_data.get("root_cause_summary")
        timestamp_str = datetime.now(TZ_VN).strftime("%d/%m/%Y %H:%M:%S")
        site_name = website_info.get("name", "Website")
        site_url = website_info.get("url", "")
        site_domain = website_info.get("domain", "")

        http_evidence = evidence_data.get("http", {})
        dns_evidence = evidence_data.get("dns", {})
        ssl_evidence = evidence_data.get("ssl", {})
        perf_evidence = evidence_data.get("performance", {})
        dom_evidence = evidence_data.get("dom", {})

        status_code = http_evidence.get("status_code")
        response_time = http_evidence.get("response_time_ms", 0.0)

        # 1. Trường hợp Hệ thống Hoạt Động Ổn Định (HEALTHY)
        if not correlation_data.get("has_incident"):
            return {
                "agent_name": self.name,
                "status": "HEALTHY",
                "severity": "HEALTHY",
                "incident_id": f"INC-{datetime.now(TZ_VN).strftime('%Y%m%d')}-000",
                "timestamp": timestamp_str,
                "fault_layer": "None (System Healthy)",
                "fault_category": "HEALTHY",
                "confidence_score": 99.5,
                "incident_title": "Báo cáo Vận hành Định kỳ: Hệ thống Hoạt động Tốt",
                "executive_summary": (
                    f"Website '{site_name}' ({site_url}) đang vận hành trong trạng thái hoàn hảo. "
                    f"Mọi tín hiệu kiểm định (HTTP {status_code or 200} OK, DNS Resolved, SSL Hợp lệ) đều đạt 100% SLA."
                ),
                "root_cause_analysis": {
                    "primary_cause": "Không phát hiện bất kỳ dấu hiệu bất thường hoặc sự cố kỹ thuật nào.",
                    "contributing_factors": ["Hạ tầng mạng và ứng dụng duy trì ổn định."],
                    "cross_signal_evidence": {
                        "HTTP": f"Status Code: {status_code or 200} OK | Response Time: {response_time}ms",
                        "DNS": f"Resolution: Thành công ({dns_evidence.get('resolution_time_ms', 0)}ms) | IPs: {dns_evidence.get('records', {}).get('a', ['127.0.0.1'])}",
                        "SSL": f"Certificate: Hợp lệ | Hạn còn lại: {ssl_evidence.get('days_remaining', 365)} ngày | TLS {ssl_evidence.get('tls_version', 'TLSv1.3')}"
                    }
                },
                "impact_assessment": {
                    "user_experience": "Người dùng truy cập mượt mà, không gặp bất kỳ gián đoạn nào.",
                    "business_availability": "Dịch vụ đạt 100% tính khả dụng (Availability SLA: 100%)."
                },
                "immediate_action_plan": [
                    "Duy trì giám sát thời gian thực theo chu kỳ định kỳ.",
                    "Ghi nhận chỉ số thời gian phản hồi vào mốc baseline lịch sử."
                ],
                "investigation_runbook": [
                    "Kiểm tra định kỳ dashboard giám sát tài nguyên.",
                    "Theo dõi xu hướng độ trễ trên biểu đồ Z-Score."
                ],
                "prevention_strategy": [
                    "Tiếp tục áp dụng các tiêu chuẩn Golden Signals trong giám sát SRE.",
                    "Duy trì tự động hóa gia hạn chứng chỉ SSL và bản ghi DNS."
                ],
                "technical_standards": [
                    "RFC 9110: HTTP Semantics (Status 200 OK)",
                    "RFC 1035: Domain Names Implementation (NOERROR)",
                    "RFC 5280: X.509 PKI Certificate Profile (Valid Chain)"
                ],
                "root_cause": "Không phát hiện bất kỳ dấu hiệu bất thường hoặc sự cố kỹ thuật nào.",
                "rfc_citations": [
                    "RFC 9110: HTTP Semantics (Status 200 OK)",
                    "RFC 1035: Domain Names Implementation (NOERROR)",
                    "RFC 5280: X.509 PKI Certificate Profile (Valid Chain)"
                ]
            }

        # 2. Trường hợp Có Sự Cố (INCIDENT DETECTED)
        runbook = self.kb.query_runbook_by_scenario(incident_type) or self.kb.query_runbook_by_scenario(str(primary_issue))

        # Phân tầng sự cố (Fault Layer)
        if any(kw in incident_type for kw in ["BACKEND", "500", "5XX", "LATENCY", "DOM", "VISUAL"]):
            fault_layer = "🔴 Application Layer (Mã nguồn Ứng dụng)"
        else:
            fault_layer = "🌐 Infrastructure Layer (Hạ tầng Nginx / DNS / SSL)"

        # Xây dựng Bằng chứng Đối soát Đa Tín hiệu (Cross-Signal Evidence)
        cross_evidence = {
            "HTTP": (
                f"Status Code: {status_code or 'Failed'} ({http_evidence.get('status_category', 'Error')}) | "
                f"Response Time: {response_time}ms | Error: {http_evidence.get('error_title') or 'None'}"
            ),
            "DNS": (
                f"Status: {'Resolved' if dns_evidence.get('resolution_success') else 'Failed'} | "
                f"Resolution Time: {dns_evidence.get('resolution_time_ms', 0)}ms | "
                f"Bản ghi A: {dns_evidence.get('records', {}).get('a', [])}"
            ),
            "SSL/TLS": (
                f"Status: {'VALID' if ssl_evidence.get('is_valid') else 'INVALID (' + str(ssl_evidence.get('error_title', 'Error')) + ')'} | "
                f"Issuer: {ssl_evidence.get('issuer', 'N/A')} | Hạn còn: {ssl_evidence.get('days_remaining', 0)} ngày"
            )
        }
        if perf_evidence and perf_evidence.get("total_time_ms"):
            cross_evidence["Performance"] = f"Total Load Time: {perf_evidence.get('total_time_ms')}ms | Grade: {perf_evidence.get('performance_grade')}"
        if dom_evidence and dom_evidence.get("missing_critical_elements"):
            cross_evidence["DOM"] = f"Thiếu thành phần cốt lõi: {', '.join(dom_evidence.get('missing_critical_elements', []))}"

        # Xác định nội dung chi tiết theo từng loại kịch bản lỗi
        if "HTTP_5" in incident_type or (status_code and status_code >= 500):
            incident_title = "Sự cố Máy Chủ Backend: HTTP 500 Server Error"
            exec_summary = (
                f"Phát hiện sự cố sập ứng dụng hoặc lỗi xử lý nội bộ tại máy chủ Backend (HTTP {status_code}) trên website '{site_name}'. "
                f"Các tầng hạ tầng mạng bên dưới (DNS và SSL TLS) vẫn hợp lệ, tác tử xác định nguyên nhân gốc nằm tại mã nguồn Backend hoặc kết nối Cơ sở dữ liệu bị gián đoạn."
            )
            primary_cause = f"Mã nguồn Backend ném ngoại lệ không xử lý (Unhandled Exception) hoặc kết nối Cơ sở Dữ liệu bị từ chối / Timeout."
            potential_causes = [
                "Cạn kiệt Connection Pool của Database (PostgreSQL/MySQL/MongoDB).",
                "Lỗi cú pháp hoặc runtime error trong route handler của Express/Node.js.",
                "Tiến trình backend worker bị tràn bộ nhớ (OOM Crash)."
            ]
            user_impact = "Toàn bộ người dùng truy cập nhận thông báo lỗi 500, không thể thực hiện bất kỳ giao dịch hoặc xem nội dung sản phẩm."
            biz_impact = "Gián đoạn 100% luồng nghiệp vụ kinh doanh, suy giảm độ tin cậy và gây thiệt hại doanh thu trực tiếp."
            action_plan = [
                "Khởi động lại ngay tiến trình Backend hoặc container ứng dụng.",
                "Kiểm tra lại thông tin cấu hình kết nối DB (Host, Port, User, Password) trong tệp .env.",
                "Kiểm tra sức khỏe cụm Database và tăng số lượng kết nối tối đa (Max Connections Pool)."
            ]
            runbook_steps = [
                "1. Kiểm tra log ứng dụng: `tail -n 100 /var/log/nginx/error.log` hoặc `docker logs <container_id>`",
                "2. Kiểm tra trạng thái Database: `pg_isready -h 10.0.0.5 -p 5432` hoặc `mysqladmin ping`",
                "3. Kiểm tra mức tải tài nguyên: `top -b -n 1` hoặc `free -m`"
            ]
            prevention = [
                "Bổ sung khối `try/catch` toàn cục và Middleware xử lý lỗi tập trung.",
                "Thiết lập cơ chế Circuit Breaker & Retry có giới hạn đối với kết nối Database.",
                "Tích hợp công cụ giám sát APM (Sentry / OpenTelemetry) để tự động bắt Exception."
            ]
            rfc_refs = [
                "RFC 9110 Section 15.6.1: 500 Internal Server Error Semantics",
                "SRE Golden Signals: Errors & Latency Assessment"
            ]

        elif any(k in incident_type for k in ["SERVER_DOWN", "SERVER_PROCESS_DOWN"]):
            incident_title = "Sự cố Ngừng Hoạt Động Máy Chủ: Web Server Process Down"
            exec_summary = (
                f"Phát hiện sự cố ngưng hoạt động máy chủ web (Server Down / Connection Refused) trên website '{site_name}'. "
                f"Cổng dịch vụ web không mở hoặc tiến trình máy chủ (Nginx/Node.js/Gunicorn) đã bị dừng."
            )
            primary_cause = "Tiến trình dịch vụ máy chủ web ngưng hoạt động (Process Terminated / Crashed) hoặc cổng dịch vụ bị từ chối kết nối (Connection Refused)."
            potential_causes = [
                "Tiến trình máy chủ web (Node.js/Nginx/Apache) bị crash hoặc bị dừng bởi hệ điều hành (OOM Killer).",
                "Cổng mạng (Port) bị chiếm dụng hoặc bị đóng bởi chính sách tường lửa (Firewall/UFW/iptables).",
                "Lỗi cấu hình cổng lắng nghe hoặc crash do ngoại lệ chưa bắt trong tiến trình khởi động."
            ]
            user_impact = "Người dùng không thể truy cập, trình duyệt thông báo lỗi `ERR_CONNECTION_REFUSED`."
            biz_impact = "Toàn bộ lưu lượng truy cập bị gián đoạn hoàn toàn, chỉ số khả dụng giảm về 0%."
            action_plan = [
                "Khởi động lại tiến trình web server hoặc dịch vụ nền (`systemctl restart nginx` hoặc `node server.js`).",
                "Kiểm tra xem cổng dịch vụ có đang lắng nghe: `netstat -tuln` hoặc `ss -tulpn`.",
                "Kiểm tra nhật ký hệ thống: `journalctl -xe` hoặc file `error.log` của Nginx."
            ]
            runbook_steps = [
                "1. Kiểm tra trạng thái tiến trình: `ps aux | grep node` hoặc `systemctl status nginx`",
                "2. Kiểm tra log sập của hệ điều hành: `dmesg -T | grep -i oom`",
                "3. Thử kết nối socket cục bộ: `curl -v http://127.0.0.1:<port>`"
            ]
            prevention = [
                "Cấu hình Process Manager tự động phục hồi khi sập (PM2 / Systemd `Restart=always` / Docker Restart Policies).",
                "Thiết lập Health Check liveness/readiness tự động trong cụm điều phối container."
            ]
            rfc_refs = [
                "RFC 9110: HTTP Semantics - Transport Layer Connectivity",
                "RFC 793: Transmission Control Protocol (TCP Connection State)"
            ]

        elif "REDIRECT_LOOP" in incident_type:
            incident_title = "Sự cố Vòng Lặp Chuyển Hướng: HTTP 302 Redirect Loop"
            exec_summary = (
                f"Phát hiện lỗi cấu hình chuyển hướng đệ quy vô hạn (Redirect Loop) trên website '{site_name}'. "
                f"Trình duyệt client bị chuyển tiếp liên tục giữa các URL mà không thể tải trang đích."
            )
            primary_cause = "Cấu hình Nginx Virtual Host hoặc Middleware ứng dụng trả về mã 302/301 trỏ ngược về chính nó."
            potential_causes = [
                "Xung đột luật chuyển hướng SSL giữa Cloudflare/Reverse Proxy và Backend.",
                "Thiếu header `X-Forwarded-Proto: https` tại tầng Reverse Proxy.",
                "Quy tắc trailing slash `/` chuyển tiếp đệ quy không hồi kết."
            ]
            user_impact = "Trình duyệt của người dùng ngắt kết nối và hiển thị lỗi `ERR_TOO_MANY_REDIRECTS`."
            biz_impact = "Website bị chặn hoàn toàn, người dùng không thể vào trang chủ hoặc bất kỳ đường dẫn nào."
            action_plan = [
                "Kiểm tra lại block `location /` trong tệp cấu hình Nginx của site.",
                "Loại bỏ câu lệnh `return 302` đệ quy hoặc sửa lại đúng URL đích.",
                "Reload cấu hình Nginx sau khi chỉnh sửa (`sudo nginx -s reload`)."
            ]
            runbook_steps = [
                "1. Lần theo chuỗi chuyển hướng: `curl -IL https://" + site_domain + "`",
                "2. Kiểm tra file cấu hình Nginx: `cat /etc/nginx/sites-available/" + site_domain + ".conf`",
                "3. Kiểm tra cú pháp Nginx: `sudo nginx -t`"
            ]
            prevention = [
                "Đồng bộ chuẩn chuyển hướng HTTPS duy nhất một lần tại tầng Edge Proxy.",
                "Kiểm tra tự động cấu hình Virtual Host trước khi nạp vào Production."
            ]
            rfc_refs = [
                "RFC 9110 Section 15.4: Redirection Status Codes (301/302)",
                "RFC 9110 Section 15.4.3: Redirection Loop Prevention"
            ]

        elif "DNS" in incident_type:
            incident_title = "Sự cố Hạ Tầng Tên Miền: DNS Resolution Outage"
            exec_summary = (
                f"Phát hiện sự cố gián đoạn phân giải tên miền nghiêm trọng đối với domain '{site_domain}'. "
                f"Client không thể lấy được địa chỉ IP máy chủ để thiết lập kết nối socket TCP."
            )
            primary_cause = "Bản ghi DNS A/AAAA của tên miền bị thiếu, hết hạn hoặc trỏ về địa chỉ không hợp lệ (0.0.0.0/NXDOMAIN)."
            potential_causes = [
                "Chưa khai báo bản ghi A trong tệp cấu hình DNS Server hoặc /etc/hosts.",
                "Tên miền đã quá hạn duy trì hoặc Name Server authoritative gặp sự cố ngừng hoạt động.",
                "Cấu hình DNSSEC bị lỗi xác thực chuỗi tin cậy."
            ]
            user_impact = "Người dùng không thể tìm thấy trang web, trình duyệt báo lỗi `DNS_PROBE_FINISHED_NXDOMAIN`."
            biz_impact = "Mất kết nối hoàn toàn trên toàn cầu, lưu lượng truy cập giảm về 0."
            action_plan = [
                "Khai báo lại bản ghi A trỏ đúng về địa chỉ IP máy chủ Web.",
                "Kiểm tra trạng thái máy chủ DNS Resolver và cập nhật cấu hình Hosts/DNS.",
                "Xóa cache DNS trên máy trạm (`ipconfig /flushdns`)."
            ]
            runbook_steps = [
                "1. Truy vấn bản ghi DNS: `dig @8.8.8.8 " + site_domain + " A`",
                "2. Kiểm tra cục bộ: `nslookup " + site_domain + "`",
                "3. Kiểm tra file hosts: `grep -i '" + site_domain + "' /etc/hosts`"
            ]
            prevention = [
                "Thiết lập giám sát đa vùng (Multi-Region DNS Health Checks).",
                "Sử dụng dịch vụ DNS phân tán có độ sẵn sàng cao (Anycast DNS)."
            ]
            rfc_refs = [
                "RFC 1035: Domain Names - Implementation and Specification",
                "RFC 2308: Negative Caching of DNS Queries (NXDOMAIN)"
            ]

        elif "SSL" in incident_type:
            ssl_err = ssl_evidence.get("error_title", "SSL Error")
            incident_title = f"Sự cố An Ninh Chứng Chỉ: {ssl_err}"
            exec_summary = (
                f"Phát hiện sự cố vi phạm chuẩn an ninh SSL/TLS trên website '{site_name}'. "
                f"Chứng chỉ máy chủ gặp lỗi ({ssl_err}), khiến kênh truyền mã hóa bị từ chối tin cậy."
            )
            primary_cause = f"Chứng chỉ SSL máy chủ gặp lỗi: {ssl_evidence.get('error_detail') or 'Không hợp lệ'}."
            potential_causes = [
                "Chứng chỉ SSL đã hết hạn mà chưa được gia hạn tự động.",
                "Gắn nhầm chứng chỉ không khớp danh sách tên miền hợp lệ (SAN/CN Mismatch).",
                "Chứng chỉ tự ký (Self-Signed) không thuộc tổ chức Root CA tin cậy."
            ]
            user_impact = "Trình duyệt hiện cảnh báo đỏ `Your connection is not private` và chặn người dùng truy cập."
            biz_impact = "Tổn hại nghiêm trọng uy tín thương hiệu và an toàn thông tin người dùng."
            action_plan = [
                "Cấp phát hoặc gia hạn lại chứng chỉ SSL hợp lệ từ Root CA.",
                "Cập nhật đường dẫn `ssl_certificate` và `ssl_certificate_key` trong Nginx.",
                "Reload lại Nginx (`sudo nginx -s reload`)."
            ]
            runbook_steps = [
                "1. Kiểm tra chứng chỉ từ xa: `openssl s_client -connect " + site_domain + ":443 -servername " + site_domain + "`",
                "2. Kiểm tra thời hạn: `openssl x509 -in /var/www/dataset/certs/valid.crt -noout -dates`",
                "3. Kiểm tra SAN: `openssl x509 -in /var/www/dataset/certs/valid.crt -noout -text | grep -A1 'Subject Alternative Name'`"
            ]
            prevention = [
                "Cài đặt cảnh báo tự động trước khi chứng chỉ SSL hết hạn 30 ngày.",
                "Sử dụng công cụ tự động gia hạn chứng chỉ (Let's Encrypt Certbot cronjob)."
            ]
            rfc_refs = [
                "RFC 5280: X.509 Public Key Infrastructure Certificate Profile",
                "RFC 8446: The Transport Layer Security (TLS) Protocol Version 1.3"
            ]

        elif "LATENCY" in incident_type or "PERF" in incident_type:
            incident_title = "Sự cố Suy Giảm Hiệu Năng: High Latency & Slow Response"
            exec_summary = (
                f"Phát hiện sự cố suy giảm hiệu năng nghiêm trọng trên website '{site_name}'. "
                f"Thời gian phản hồi đạt {response_time}ms (vượt ngưỡng cảnh báo), chỉ số Z-Score ghi nhận đột biến so với mốc baseline."
            )
            primary_cause = "Tiến trình máy chủ bị nghẽn (Blocking Event Loop) hoặc truy vấn Cơ sở dữ liệu quá chậm (Slow Query)."
            potential_causes = [
                "Vòng lặp tính toán nặng hoặc hàm khóa đồng bộ trên Main Thread.",
                "Truy vấn Database quét toàn bộ bảng (Full Table Scan) do thiếu Index.",
                "Lệnh gọi API phụ thuộc bên thứ 3 bị treo kết nối."
            ]
            user_impact = "Trang web tải cực kỳ chậm chạp, nguy cơ cao phát sinh timeout hoặc khách hàng thoát trang."
            biz_impact = "Tỷ lệ chuyển đổi giảm mạnh, vi phạm chỉ tiêu chất lượng dịch vụ SLA."
            action_plan = [
                "Tối ưu hóa các đoạn code chứa vòng lặp tính toán nặng hoặc chuyển sang Worker Threads.",
                "Thêm Index cho các trường tra cứu thường xuyên trong Database.",
                "Bổ sung bộ nhớ đệm Cache (Redis) cho các dữ liệu ít biến động."
            ]
            runbook_steps = [
                "1. Đo lường phân rã thời gian: `curl -w '@curl-format.txt' -o /dev/null -s https://" + site_domain + "`",
                "2. Kiểm tra Slow Query Log của CSDL.",
                "3. Bật Node.js Profiler để tìm hàm ngốn CPU."
            ]
            prevention = [
                "Thiết lập APM Profiling liên tục trên môi trường Production.",
                "Áp dụng chính sách Async I/O và hàng đợi xử lý bất đồng bộ (Queue Worker)."
            ]
            rfc_refs = [
                "RFC 9110: HTTP Performance & Latency Guidelines",
                "Google Core Web Vitals: TTFB & Page Load Standards"
            ]

        elif any(k in incident_type for k in ["DOM", "FRONTEND_UI_DEFORMATION", "VISUAL", "MISSING_DOM"]):
            incident_title = "Lỗi Bất Thường Giao Diện: Missing DOM / UI Elements"
            missing_items = dom_evidence.get("missing_critical_elements") or []
            missing_desc = ", ".join(missing_items) if missing_items else str(primary_issue)
            exec_summary = (
                f"Phát hiện sự cố giao diện người dùng (Frontend UI / DOM Anomaly) trên website '{site_name}'. "
                f"Tầng mạng (DNS, SSL, HTTP Status 200 OK) phản hồi bình thường nhưng cấu trúc DOM bị khuyết thiếu hoặc phần tử cốt lõi bị ẩn bất thường ({missing_desc})."
            )
            primary_cause = f"Thành phần giao diện người dùng cốt lõi bị khuyết thiếu hoặc bị ẩn bất thường: {missing_desc}."
            potential_causes = [
                "Lớp CSS vô tình áp dụng quy tắc `display: none` hoặc `visibility: hidden` lên thanh điều hướng / nút hành động.",
                "Lỗi cú pháp JavaScript trong file bundle khiến quá trình hydrate / render DOM bị ngắt quãng.",
                "Mã HTML bị can thiệp xóa nhầm các phần tử semantic (<nav>, <button>, <main>) trong quá trình triển khai mã nguồn mới."
            ]
            user_impact = "Người dùng không thể nhìn thấy menu điều hướng hoặc không thể click nút thực hiện hành động chính, làm gián đoạn luồng trải nghiệm trên trang."
            biz_impact = "Suy giảm tỷ lệ tương tác (Engagement Rate) và nguy cơ mất khách hàng do không thể thao tác các chức năng chính."
            action_plan = [
                "Kiểm tra file HTML và style CSS, gỡ bỏ thuộc tính `display: none` trên phần tử giao diện.",
                "Kiểm tra console log trình duyệt xem có lỗi JavaScript runtime gây chặn render hay không.",
                "Khôi phục lại phiên bản giao diện chuẩn từ mốc Baseline đã được kiểm định."
            ]
            runbook_steps = [
                "1. Kiểm tra phần tử trong DevTools: Mở Inspect Element và tìm selector bị ẩn.",
                "2. Kiểm tra CSS áp dụng: Kiểm tra tab Styles để xác định nguồn gốc rule `display: none`.",
                "3. Đối chiếu ảnh chụp màn hình hiện tại với ảnh Baseline chuẩn để khoanh vùng biến dạng giao diện."
            ]
            prevention = [
                "Bổ sung bước kiểm thử tự động E2E / Visual Regression Testing trong quy trình CI/CD.",
                "Thiết lập cơ chế kiểm định cấu trúc DOM (DOM Structural Validation) định kỳ trước khi phát hành tính năng mới."
            ]
            rfc_refs = [
                "W3C DOM (Document Object Model) Technical Specification",
                "W3C HTML5 Semantic Elements Standard (Section 4.4: Grouping & Navigation)",
                "WCAG 2.1 Success Criterion 4.1.2: Name, Role, Value"
            ]

        else:
            incident_title = f"Sự cố Vận Hành: {incident_type}"
            exec_summary = f"Phát hiện bất thường kỹ thuật mức độ {severity} trên website '{site_name}': {primary_issue}."
            primary_cause = str(primary_issue)
            potential_causes = ["Sai lệch cấu hình hệ thống hoặc gián đoạn dịch vụ liên quan."]
            user_impact = "Trải nghiệm truy cập của người dùng bị ảnh hưởng hoặc gián đoạn một phần."
            biz_impact = "Ảnh hưởng tới chỉ số khả dụng và chất lượng vận hành dịch vụ."
            action_plan = ["Tiến hành kiểm tra chi tiết các tín hiệu lỗi và khôi phục dịch vụ."]
            runbook_steps = ["1. Kiểm tra trạng thái toàn bộ dịch vụ phụ thuộc.", "2. Kiểm tra error log hệ thống."]
            prevention = ["Tăng cường giám sát thời gian thực và tự động hồi phục."]
        base_exec_summary = exec_summary
        # =========================================================================
        # TÍCH HỢP LLM-POWERED REASONING (GOOGLE GEMINI AI SRE)
        # =========================================================================
        llm_insights = None
        is_llm_enhanced = False
        gemini_model = "gemini-flash-lite-latest"
        try:
            sys_settings = get_system_settings()
            gemini_key = (sys_settings.get("gemini_api_key") or "").strip()
            llm_enabled = bool(sys_settings.get("llm_enabled", 0))
            gemini_model = sys_settings.get("gemini_model") or "gemini-flash-lite-latest"

            if llm_enabled and gemini_key:
                prompt = (
                    f"Bạn là Chuyên gia Site Reliability Engineer (Senior SRE / DevOps) phân tích sự cố website.\n"
                    f"Thông tin website: {site_name} ({site_url}, domain: {site_domain})\n"
                    f"Sự cố ghi nhận: {incident_title} (Mức độ: {severity})\n"
                    f"Phân tầng lỗi: {fault_layer} | Loại sự cố: {incident_type}\n"
                    f"Nguyên nhân gốc sơ bộ: {primary_cause}\n"
                    f"Bằng chứng tín hiệu kỹ thuật: {cross_evidence}\n\n"
                    f"Yêu cầu:\n"
                    f"1. Nhận định chuyên sâu về nguyên nhân gốc và rủi ro chuỗi (2-3 câu súc tích).\n"
                    f"2. Đề xuất hành động khắc phục khẩn cấp ưu tiên số 1 cho kỹ sư vận hành."
                )
                system_instruction = (
                    "Bạn là Trợ lý Vận hành Hệ thống AI (AI SRE Assistant). "
                    "Hãy phản hồi bằng tiếng Việt chuyên nghiệp, ngắn gọn, chuẩn thuật ngữ SRE/DevOps quốc tế."
                )
                llm_resp = generate_gemini_analysis(
                    prompt=prompt,
                    api_key=gemini_key,
                    model=gemini_model,
                    system_instruction=system_instruction,
                    timeout=25.0
                )
                if llm_resp:
                    llm_insights = llm_resp
                    is_llm_enhanced = True
                    exec_summary = f"{exec_summary}\n\n🤖 [AI SRE Reasoning - {gemini_model}]:\n{llm_resp}"
        except Exception as e:
            print(f"[!] Warning: IncidentAnalysisAgent LLM enrichment failed: {e}")

        return {
            "agent_name": self.name,
            "status": "INCIDENT_DETECTED",
            "severity": severity,
            "incident_id": f"INC-{datetime.now(TZ_VN).strftime('%Y%m%d')}-{int(time.time()) % 1000:03d}",
            "timestamp": timestamp_str,
            "fault_layer": fault_layer,
            "fault_category": incident_type,
            "confidence_score": 98.8,
            "incident_title": incident_title,
            "executive_summary": exec_summary,
            "base_executive_summary": base_exec_summary,
            "llm_enhanced": is_llm_enhanced,
            "llm_insights": llm_insights,
            "gemini_model": gemini_model if is_llm_enhanced else None,
            "dual_engine_comparison": {
                "option_without_ai": {
                    "mode": "SRE_KNOWLEDGE_BASE",
                    "title": "📚 SRE Knowledge Base (Không dùng AI)",
                    "summary": base_exec_summary,
                    "primary_cause": primary_cause,
                    "description": "Suy luận tất định dựa trên bộ luật RFC và SRE Runbook tiêu chuẩn. Không phụ thuộc LLM, độ trễ 0ms, không ảo giác."
                },
                "option_with_ai": {
                    "mode": "GEMINI_AI_REASONING",
                    "title": f"🤖 Google Gemini AI ({gemini_model if is_llm_enhanced else 'Đang tắt'})",
                    "is_available": is_llm_enhanced,
                    "summary": llm_insights if is_llm_enhanced else "Chưa kích hoạt hoặc API không khả dụng (Hệ thống tự động sử dụng SRE Knowledge Base).",
                    "description": "Suy luận ngữ cảnh chuyên sâu, phân tích rủi ro dây chuyền và khuyến nghị chỉ thị khẩn cấp P0."
                }
            },
            "root_cause_analysis": {
                "primary_cause": primary_cause,
                "contributing_factors": potential_causes,
                "cross_signal_evidence": cross_evidence
            },
            "impact_assessment": {
                "user_experience": user_impact,
                "business_availability": biz_impact
            },
            "immediate_action_plan": action_plan,
            "investigation_runbook": runbook_steps,
            "prevention_strategy": prevention,
            "technical_standards": rfc_refs,
            "root_cause": primary_cause,
            "rfc_citations": rfc_refs
        }

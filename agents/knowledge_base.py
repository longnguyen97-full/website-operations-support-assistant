"""
Operational Knowledge Base (Tri thức Vận hành & Tiêu chuẩn Kỹ thuật SRE)
Cung cấp ngữ cảnh chuyên môn, chuẩn giao thức RFC và sổ tay khắc phục sự cố (Runbooks)
cho các tác tử Agentic AI suy luận và phân tích nguyên nhân gốc (RCA).
"""

from typing import Dict, Any, Optional, List

# 1. Bảng tra cứu chuẩn giao thức RFC (Protocol Standards Reference)
RFC_STANDARDS = {
    "RFC_9110": {
        "title": "RFC 9110: HTTP Semantics",
        "scope": "HTTP Status Codes, Cache-Control, Redirects, Content Negotiation",
        "guidelines": {
            "2xx": "Yêu cầu được tiếp nhận, hiểu và chấp nhận thành công bởi máy chủ.",
            "3xx": "Client cần thực hiện thêm hành động để hoàn tất yêu cầu (Redirection). Cần kiểm soát số bước redirect <= 5 để tránh Redirect Loop.",
            "4xx": "Lỗi xuất phát từ phía Client (cú pháp sai, thiếu quyền, đường dẫn không tồn tại).",
            "5xx": "Máy chủ gặp lỗi nội bộ hoặc không thể đáp ứng yêu cầu hợp lệ từ client."
        }
    },
    "RFC_1035": {
        "title": "RFC 1035: Domain Names - Implementation and Specification",
        "scope": "DNS Query, Resource Records (A, AAAA, CNAME, MX, TXT), RCODEs",
        "guidelines": {
            "NOERROR": "Phân giải tên miền thành công, bản ghi tồn tại.",
            "NXDOMAIN": "Tên miền không tồn tại trên hệ thống Authoritative DNS Server.",
            "SERVFAIL": "Máy chủ tên miền gặp sự cố khi xử lý truy vấn.",
            "REFUSED": "Máy chủ DNS từ chối thực hiện truy vấn do chính sách bảo mật."
        }
    },
    "RFC_5280": {
        "title": "RFC 5280: X.509 PKI Certificate & CRL Profile",
        "scope": "SSL/TLS Certificate Validity, Issuer Chain, Common Name, SANs",
        "guidelines": {
            "VALIDITY_PERIOD": "Chứng chỉ chỉ hợp lệ trong khoảng thời gian notBefore đến notAfter.",
            "TRUST_CHAIN": "Chứng chỉ phải được ký bởi Root CA hoặc Intermediate CA nằm trong Trusted Store của hệ điều hành/trình duyệt.",
            "SAN_MATCH": "Tên miền truy cập phải khớp chính xác với CN hoặc ít nhất một mục trong Subject Alternative Names."
        }
    },
    "RFC_8446": {
        "title": "RFC 8446: The Transport Layer Security (TLS) Protocol Version 1.3",
        "scope": "Secure Cryptographic Handshake, Cipher Suites, 0-RTT",
        "guidelines": {
            "HANDSHAKE": "Quá trình bắt tay mật mã thiết lập kênh truyền bảo mật giữa Client và Server.",
            "DEPRECATION": "TLS 1.0 và TLS 1.1 đã bị loại bỏ vì lý do an toàn; hệ thống khuyến nghị sử dụng tối thiểu TLS 1.2 hoặc TLS 1.3."
        }
    }
}

# 2. Sổ tay Xử lý Sự cố Kỹ thuật SRE (SRE Incident Runbooks)
INCIDENT_RUNBOOKS: Dict[str, Dict[str, Any]] = {
    "HTTP_500_INTERNAL_ERROR": {
        "title": "Sự cố HTTP 500 Internal Server Error",
        "rfc_ref": "RFC 9110 Section 15.6.1",
        "likely_causes": [
            "Lỗi ngoại lệ chưa được bắt (Unhandled Exception) trong mã nguồn Backend.",
            "Cạn kiệt Connection Pool của Cơ sở dữ liệu (PostgreSQL / MySQL).",
            "Tràn bộ nhớ RAM hoặc CPU Worker Backend đạt 100%."
        ],
        "investigation_steps": [
            "1. Kiểm tra log ứng dụng (Application Logs / Sentry / CloudWatch) tìm Stacktrace gần nhất.",
            "2. Kiểm tra trạng thái Database connection pool và số lượng active connections.",
            "3. Kiểm tra mức sử dụng tài nguyên CPU, RAM và Disk I/O trên cụm máy chủ ứng dụng."
        ],
        "remediation_actions": [
            "Khởi động lại Worker / Container Backend bị treo.",
            "Tăng kích thước Database Connection Pool hoặc thêm Read Replica.",
            "Rollback bản phát hành gần nhất nếu lỗi xuất hiện ngay sau đợt triển khai."
        ]
    },
    "HTTP_502_BAD_GATEWAY": {
        "title": "Sự cố HTTP 502 Bad Gateway",
        "rfc_ref": "RFC 9110 Section 15.6.3",
        "likely_causes": [
            "Tiến trình Backend (Node.js/Python/PHP-FPM) bị sập hoặc không lắng nghe trên cổng upstream.",
            "Nginx / HAProxy Reverse Proxy cấu hình sai địa chỉ upstream IP hoặc Port.",
            "Firewall / Security Group chặn kết nối nội bộ giữa Proxy và Backend."
        ],
        "investigation_steps": [
            "1. Kiểm tra tiến trình backend service bằng `systemctl status` hoặc `docker ps`.",
            "2. Kiểm tra error log của Nginx (`/var/log/nginx/error.log`).",
            "3. Thử gọi trực tiếp `curl -I http://127.0.0.1:<backend_port>` từ máy chủ proxy."
        ],
        "remediation_actions": [
            "Khởi động lại dịch vụ backend và cấu hình tự động hồi phục (Auto-restart / PM2 / K8s restartPolicy).",
            "Sửa lại block upstream trong file cấu hình reverse proxy."
        ]
    },
    "HTTP_REDIRECT_LOOP": {
        "title": "Sự cố Vòng lặp Chuyển hướng (HTTP 302/301 Redirect Loop)",
        "rfc_ref": "RFC 9110 Section 15.4",
        "likely_causes": [
            "Xung đột luật chuyển hướng SSL giữa Cloudflare/Reverse Proxy và Backend.",
            "Thiếu cấu hình header `X-Forwarded-Proto: https` tại tầng Proxy.",
            "Quy tắc trailing slash `/` chuyển tiếp đệ quy không hồi kết."
        ],
        "investigation_steps": [
            "1. Lần theo chuỗi chuyển hướng `curl -IL <url>` để ghi nhận các bước redirect.",
            "2. Kiểm tra chế độ SSL trên CDN/Cloudflare (chuyển sang Full/Strict nếu đang ở Flexible).",
            "3. Kiểm tra file cấu hình `.htaccess`, `nginx.conf` hoặc middleware redirect."
        ],
        "remediation_actions": [
            "Cấu hình `proxy_set_header X-Forwarded-Proto $scheme;` trên Nginx.",
            "Đồng bộ chuẩn URL kết thúc (trailing slash) trong toàn bộ router."
        ]
    },
    "DNS_RESOLUTION_FAILURE": {
        "title": "Sự cố Lỗi Phân giải Tên miền (DNS Resolution Outage)",
        "rfc_ref": "RFC 1035",
        "likely_causes": [
            "Tên miền chưa được trỏ bản ghi A/AAAA trên Name Server.",
            "Hết hạn duy trì tên miền (Domain Expiration).",
            "Name Server của nhà cung cấp DNS gặp sự cố ngừng hoạt động (DDoS / Outage)."
        ],
        "investigation_steps": [
            "1. Sử dụng lệnh `dig @8.8.8.8 <domain>` để kiểm tra bản ghi từ Google DNS.",
            "2. Kiểm tra trạng thái WHOIS của tên miền xem có bị khoá (ClientHold) hay quá hạn không.",
            "3. Kiểm tra bản ghi NS và DNSSEC."
        ],
        "remediation_actions": [
            "Cập nhật bản ghi A trỏ về đúng IP máy chủ trên trang quản trị DNS.",
            "Gia hạn tên miền ngay lập tức nếu đã hết hạn."
        ]
    },
    "SSL_CERTIFICATE_EXPIRED": {
        "title": "Sự cố Chứng chỉ SSL/TLS Quá hạn hoặc Không hợp lệ",
        "rfc_ref": "RFC 5280 Section 4.1.2.5",
        "likely_causes": [
            "Chứng chỉ SSL đã hết hạn mà chưa được gia hạn.",
            "Cronjob Let's Encrypt Certbot tự động gia hạn bị lỗi quyền hoặc xung đột cổng 80.",
            "Gắn nhầm chứng chỉ tự ký (Self-signed) lên môi trường Production."
        ],
        "investigation_steps": [
            "1. Kiểm tra ngày hết hạn qua `openssl s_client -connect <domain>:443 -servername <domain>`.",
            "2. Kiểm tra log certbot tại `/var/log/letsencrypt/letsencrypt.log`."
        ],
        "remediation_actions": [
            "Chạy lệnh gia hạn cưỡng bức `certbot renew --force-renewal`.",
            "Cài đặt chứng chỉ số hợp lệ từ tổ chức CA được công nhận."
        ]
    },
    "PERF_HIGH_LATENCY_SPIKE": {
        "title": "Sự cố Đột biến Độ trễ Phản hồi (High Latency Spike)",
        "rfc_ref": "RFC 9110 / SRE Golden Signals",
        "likely_causes": [
            "Truy vấn CSDL nặng quét toàn bộ bảng (Full Table Scan) thiếu Index.",
            "Các lệnh gọi API đồng bộ tới bên thứ 3 (Payment/SMS) bị tắc nghẽn.",
            "Tải CPU tăng vọt do rò rỉ bộ nhớ hoặc tiến trình nền nặng."
        ],
        "investigation_steps": [
            "1. Kiểm tra Slow Query Log của Database.",
            "2. Bật APM (Application Performance Monitoring) đo lường thời gian xử lý từng hàm.",
            "3. Kiểm tra độ lệch chuẩn Z-Score trên chuỗi thời gian lịch sử."
        ],
        "remediation_actions": [
            "Thêm tầng Cache Redis/Memcached cho các truy vấn dữ liệu tĩnh.",
            "Chuyển các tác vụ bên thứ 3 sang kiến trúc hàng đợi bất đồng bộ (Celery / BullMQ)."
        ]
    },
    "DOM_STRUCTURAL_CORRUPTION": {
        "title": "Sự cố Khiếm khuyết Cấu trúc Giao diện DOM / Missing Assets",
        "rfc_ref": "W3C HTML5 Standard / DOM Level 3",
        "likely_causes": [
            "Lỗi biên dịch bundle Frontend (Vite/Webpack) làm mất file CSS (404 Error).",
            "Mã JavaScript bị runtime error khiến quá trình render component (React/Vue) bị ngắt quãng.",
            "Template HTML bị xoá nhầm các phần tử cốt lõi (Heading <h1>, nút bấm CTA)."
        ],
        "investigation_steps": [
            "1. Kiểm tra Console Error log trong Playwright Browser.",
            "2. Kiểm tra Network Tab tìm kiếm các tài nguyên trả về mã 404/500.",
            "3. Chụp ảnh màn hình so sánh với ảnh mốc chuẩn (Visual Regression)."
        ],
        "remediation_actions": [
            "Đồng bộ lại tài nguyên build artifact lên CDN / Nginx static directory.",
            "Sửa lỗi runtime JavaScript trong component giao diện."
        ]
    }
}

class OperationalKnowledgeBase:
    """Kho tri thức chuyên môn phục vụ các Agent suy luận ngữ cảnh."""

    @staticmethod
    def get_rfc_info(rfc_key: str) -> Optional[Dict[str, Any]]:
        """Lấy thông tin chuẩn RFC tương ứng."""
        return RFC_STANDARDS.get(rfc_key)

    @staticmethod
    def query_runbook_by_scenario(scenario_or_issue: str) -> Optional[Dict[str, Any]]:
        """Truy vấn sổ tay hướng dẫn xử lý sự cố theo từ khóa hoặc mã kịch bản."""
        key = scenario_or_issue.upper()
        for k, runbook in INCIDENT_RUNBOOKS.items():
            if k in key or any(word in key for word in k.split('_') if len(word) > 3):
                return runbook
        return None

    @staticmethod
    def get_all_runbooks() -> Dict[str, Dict[str, Any]]:
        """Lấy toàn bộ danh mục Runbook."""
        return INCIDENT_RUNBOOKS

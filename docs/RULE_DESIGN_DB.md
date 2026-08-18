# RULE_DESIGN_DB.md

Quy định kỹ thuật và chuẩn thiết kế Cơ sở dữ liệu (Database Design Rules) cho hệ thống Giám sát Website sử dụng Agentic AI.

## 1. Định hướng Công nghệ và Lưu trữ

* **Hệ quản trị CSDL:** SQLite (sử dụng module chuẩn `sqlite3` của Python), lưu trữ tại thư mục chuyên biệt `data/monitoring.db`.
* **Mô hình hóa dữ liệu:** Kết hợp giữa dữ liệu quan hệ (Relational data) cho việc quản lý cấu hình, định danh website và dữ liệu bán cấu trúc (Semi-structured/JSON) để lưu trữ linh hoạt kết quả chi tiết từ các công cụ kiểm tra (HTTP, DNS, SSL/TLS).
* **Quy chuẩn mã hóa:** Toàn bộ dữ liệu văn bản sử dụng chuẩn mã hóa **UTF-8**, định dạng thời gian lưu trữ theo chuẩn **ISO 8601 (UTC+7)**.

---

## 2. Quy tắc Đặt tên (Naming Conventions)

* **Tên bảng (Table Name):** Sử dụng danh từ số nhiều, viết thường, phân tách bằng dấu gạch dưới (`snake_case`). Ví dụ: `monitoring_logs`, `milestone_baselines`.
* **Tên cột (Column Name):** Sử dụng chữ thường, ngắn gọn, mô tả rõ nghĩa, phân tách bằng dấu gạch dưới (`snake_case`). Ví dụ: `website_name`, `http_status_code`, `created_at`.
* **Khóa chính (Primary Key):** Mọi bảng bắt buộc phải có cột khóa chính dạng số nguyên tự tăng mang tên `id` (`INTEGER PRIMARY KEY AUTOINCREMENT`).

---

## 3. Đặc tả Schema Chi tiết

### 3.1. Bảng `monitoring_logs` (Lưu vết kiểm tra định kỳ)

Bảng này lưu trữ toàn bộ lịch sử thực thi của các Probe Agent qua mỗi lần quét, phục vụ cho việc thống kê, phát hiện bất thường và làm đầu vào tương quan sự cố cho Agentic AI.

* `id`: Khóa chính, tự tăng.
* `website_name`: Tên định danh của website (TEXT, bắt buộc).
* `url`: Đường dẫn URL đầy đủ được kiểm tra (TEXT).
* `domain`: Tên miền chính phục vụ truy vấn DNS (TEXT).
* `timestamp`: Thời điểm thực hiện kiểm tra (TEXT, định dạng ISO 8601 UTC).
* `http_status_code`: Mã trạng thái HTTP trả về (INTEGER).
* `http_latency_ms`: Thời gian phản hồi HTTP tính bằng mili-giây (REAL).
* `http_is_expected`: Cờ xác định mã trạng thái có khớp với cấu hình kỳ vọng hay không (BOOLEAN).
* `http_data_json`: Chuỗi JSON lưu toàn bộ chi tiết HTTP (redirect chain, headers, v.v.) (TEXT).
* `dns_resolved`: Trạng thái phân giải DNS thành công hay thất bại (BOOLEAN).
* `dns_latency_ms`: Thời gian phân giải DNS (REAL).
* `dns_is_load_balancing`: Cờ phân biệt thay đổi DNS do load balancing hay bất thường (BOOLEAN).
* `dns_data_json`: Chuỗi JSON lưu chi tiết các bản ghi A, AAAA, CNAME, MX, TXT (TEXT).
* `ssl_is_valid`: Trạng thái chứng chỉ SSL/TLS có hợp lệ hay không (BOOLEAN).
* `ssl_days_remaining`: Số ngày còn lại trước khi chứng chỉ hết hạn (INTEGER).
* `ssl_tls_version`: Phiên bản TLS được hỗ trợ (TEXT).
* `ssl_data_json`: Chuỗi JSON lưu chi tiết chứng chỉ (issuer, SANs, chain, v.v.) (TEXT).
* `overall_status`: Trạng thái tổng hợp của lần kiểm tra (`HEALTHY`, `WARNING`, `CRITICAL`).

### 3.2. Bảng `milestone_baselines` (Quản lý Mốc chuẩn)

Bảng này lưu trữ cấu hình mốc chuẩn (baseline) theo từng thời điểm để hệ thống đối chiếu, phân tích sai lệch cấu hình DNS hoặc trạng thái hệ thống có kế hoạch.

* `id`: Khóa chính, tự tăng.
* `website_name`: Tên website áp dụng mốc chuẩn (TEXT).
* `domain`: Tên miền liên quan (TEXT).
* `created_at`: Thời điểm mốc chuẩn được ghi nhận (TEXT, ISO 8601 UTC).
* `baseline_dns_json`: Chuỗi JSON lưu giá trị baseline các bản ghi DNS (TEXT).
* `expected_http_status`: Mã trạng thái HTTP kỳ vọng chuẩn (INTEGER).
* `note`: Ghi chú diễn giải ngữ cảnh mốc chuẩn (Ví dụ: "Trước đợt bảo trì hệ thống", "Sau khi cấu hình Cloudflare") (TEXT).
* `is_active`: Cờ xác định mốc chuẩn nào đang được kích hoạt hiệu lực sử dụng (BOOLEAN).

---

## 4. Nguyên tắc Vận hành và Duy trì Dữ liệu (Data Governance)

* **Tính toàn vẹn:** Các thao tác ghi dữ liệu từ Probe Agent phải tuân thủ cơ chế đóng gói Transaction để tránh xung đột ghi tệp cục bộ trên SQLite.
* **Chính sách lưu trữ (Data Retention):** Dữ liệu log kiểm tra (`monitoring_logs`) cần có cơ chế dọn dẹp định kỳ (Purge) đối với các bản ghi quá cũ (ví dụ: giữ lại tối đa 30 ngày) nhằm kiểm soát dung lượng file database.
* **Quản lý Baseline:** Chỉ cho phép tồn tại một mốc chuẩn `is_active = TRUE` cho mỗi website/domain tại một thời điểm; khi tạo mốc chuẩn mới, các mốc cũ sẽ chuyển về trạng thái `FALSE` hoặc được lưu lịch sử truy vết.
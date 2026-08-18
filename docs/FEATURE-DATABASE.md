### 📦 CHI TIẾT TÍNH NĂNG CƠ SỞ DỮ LIỆU (DATABASE & BASELINE)

#### 1. Hệ quản trị CSDL: SQLite (`data/monitoring.db`)
* Sử dụng module chuẩn `sqlite3` của Python, gọn nhẹ, hoàn toàn cục bộ, không phụ thuộc server CSDL ngoài.
* Toàn bộ mốc thời gian lưu trữ chuẩn hóa theo **ISO 8601 (UTC+7)**.

#### 2. Cấu trúc các bảng (Schema):
* **`websites` (Master Table):** Quản lý danh mục website, URL, domain, mã HTTP kỳ vọng (`expected_status`).
* **`milestone_baselines`:** Lưu trữ các mốc chuẩn cấu hình DNS/HTTP (Baseline) theo từng giai đoạn, hỗ trợ cờ `is_active` để chọn mốc chuẩn đối soát.
* **`monitoring_logs`:** Lưu trữ lịch sử tất cả các lần quét (Timestamp, HTTP Status, Latency, DNS Resolved, SSL Days Left, Full Signals JSON, Overall Status).
* **`system_settings` (Dynamic Config):** Lưu toàn bộ cấu hình động có thể thay đổi tại runtime từ giao diện quản trị (SMTP Server, Port, App Password, Recipient Emails, Alert Flags, Cooldown, Daily Health Report, Scheduler Interval, Retention Days, SSL Warning Days).

#### 3. Phân định Cấu hình Tĩnh (Static) vs Động (Dynamic):
* **Static Config (`.env` & `config.py`):** Múi giờ, đường dẫn file DB, timeout mạng cố định (HTTP/DNS/SSL), User-Agent, giá trị bí mật & fallback mặc định.
* **Dynamic Config (`system_settings` trong SQLite):** Cấu hình linh hoạt được quản trị viên điều chỉnh trực tiếp trên giao diện trang `pages/1_⚙️_Configuration.py`.

#### 4. Chính sách Vận hành (Data Governance):
* **Data Retention Policy:** Tự động dọn dẹp các bản ghi log cũ hơn số ngày quy định (`purge_old_logs(data_retention_days)`).
* **Seeding tự động:** Tự động nạp danh sách website mẫu ban đầu từ `target_websites.json` khi khởi tạo DB lần đầu.

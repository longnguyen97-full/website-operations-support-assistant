### 📦 CHI TIẾT TÍNH NĂNG CƠ SỞ DỮ LIỆU (DATABASE & BASELINE)

#### 1. Hệ quản trị CSDL: SQLite (`data/monitoring.db`)
* Sử dụng module chuẩn `sqlite3` của Python, gọn nhẹ, hoàn toàn cục bộ, không phụ thuộc server CSDL ngoài.
* Toàn bộ mốc thời gian lưu trữ chuẩn hóa theo **ISO 8601 (UTC+7)**.

#### 2. Cấu trúc các bảng (Schema):
* **`websites` (Master Table):** Quản lý danh mục website, URL, domain, mã HTTP kỳ vọng (`expected_status`).
* **`milestone_baselines`:** Lưu trữ các mốc chuẩn cấu hình DNS/HTTP (Baseline) theo từng giai đoạn, hỗ trợ cờ `is_active` để chọn mốc chuẩn đối soát.
* **`monitoring_logs`:** Lưu trữ lịch sử tất cả các lần quét (Timestamp, HTTP Status, Latency, DNS Resolved, SSL Days Left, Full Signals JSON, Overall Status).
* **`email_settings`:** Lưu cấu hình máy chủ SMTP và các điều kiện gửi cảnh báo email.

#### 3. Chính sách Vận hành (Data Governance):
* **Data Retention Policy:** Tự động dọn dẹp các bản ghi log cũ hơn 30 ngày (`purge_old_logs(30)`).
* **Seeding tự động:** Tự động nạp danh sách website mẫu ban đầu từ `target_websites.json` khi khởi tạo DB lần đầu.

### 📦 CHI TIẾT ĐÃ TRIỂN KHAI: HỆ THỐNG EMAIL CẢNH BÁO & BÁO CÁO ĐỊNH KỲ

#### 1. Module Gửi Email: `notifications/email_service.py`
* **Giao thức SMTP tiêu chuẩn:** Hỗ trợ chuẩn cổng `587` (STARTTLS) và cổng `465` (SSL), hoạt động trơn tru với **Gmail**, Outlook, Custom SMTP Server.
* **Email Template HTML Cảnh báo Sự cố (Incident Alerts):**
  * Cảnh báo `🚨 CRITICAL` (Website Down, HTTP lỗi, DNS thất bại, SSL hết hạn).
  * Cảnh báo `⚠️ WARNING` (SSL sắp hết hạn $\le 14$ ngày, sai mã HTTP kỳ vọng).
  * Thông báo `✅ RECOVERY` (Dịch vụ đã tự phục hồi hoạt động bình thường sau sự cố).
* **Email Template HTML Báo cáo Định kỳ (Periodic Health Digest):**
  * Tổng hợp KPI toàn diện trong 24 giờ qua: Tỷ lệ Uptime/Healthy %, Tổng số lượt quét, Số lần sự cố.
  * Bảng sức khỏe chi tiết từng website: Mã HTTP, Độ trễ HTTP & DNS, Hạn chứng chỉ SSL.
  * Danh sách các sự cố đáng chú ý trong kỳ.
* **Cơ chế chống spam (Cooldown):** Ngăn chặn gửi dồn dập email cho cùng 1 sự cố trong chu kỳ quét nền (mặc định chờ 15 phút giữa các lần cảnh báo lặp lại).

#### 2. Lưu trữ Cấu hình CSDL: Bảng `email_settings` trong `database/db.py`
* Lưu trữ các thông số: Máy chủ SMTP, Cổng, Email người gửi, Mật khẩu ứng dụng (App Password), Danh sách email người nhận.
* Cấu hình báo cáo định kỳ: `enable_daily_report`, `daily_report_time` (mặc định 08:00 sáng), `last_report_sent_at`.

#### 3. Tích hợp Lập lịch tự động: `scheduler/monitor_scheduler.py`
* **Periodic Probes Job:** Quét định kỳ tất cả website và gửi alert tức thời nếu có sự cố.
* **Daily Scheduled Report Job:** Kiểm tra mỗi phút; khi tới giờ cấu hình (ví dụ 08:00 AM) sẽ tự động kích hoạt tổng hợp dữ liệu và gửi Email Báo cáo Sức khỏe Hệ thống 24h qua tới toàn bộ người nhận.

#### 4. Giao diện Quản trị Dashboard: `ui.py`
* **Tab 📧 Cấu hình Email:**
  * Bật/Tắt gửi email cảnh báo và Báo cáo định kỳ hàng ngày.
  * Tùy chỉnh giờ gửi báo cáo (ví dụ `08:00`).
  * Nút **"🧪 Gửi Email Thử Nghiệm"**: Kiểm tra kết nối SMTP.
  * Nút **"📊 Gửi Báo Cáo Định Kỳ 24h Ngay"**: Xuất và gửi email báo cáo tức thì.
* **Tab 📈 Lịch sử & Xu hướng:**
  * Khối mở rộng xem trước trực tiếp bản tóm tắt Báo cáo Sức khỏe Hệ thống 24h qua ngay trên trình duyệt.

---

### 🚀 Hướng dẫn trải nghiệm nhanh
1. Mở giao diện Dashboard Streamlit (`http://localhost:8501`).
2. Chuyển sang tab **"📧 Cấu hình Email"**.
3. Nhập Email gửi, App Password và danh sách Email nhận.
4. Bấm **"📊 Gửi Báo Cáo Định Kỳ 24h Ngay"** để nhận ngay bản báo cáo tổng hợp sức khỏe hệ thống qua hòm thư của bạn!
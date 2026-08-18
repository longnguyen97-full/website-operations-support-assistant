### 📦 CHI TIẾT ĐÃ TRIỂN KHAI

#### 1. Cài đặt thư viện:
* Đã thêm `apscheduler` vào `pyproject.toml` qua `uv`.

#### 2. Module Scheduler: [scheduler/monitor_scheduler.py]
* **`BackgroundScheduler`:** Chạy ngầm đa luồng (daemon thread) không gây block giao diện Streamlit.
* **Tự động quét toàn bộ Website định kỳ:**
  * Lấy danh sách website từ CSDL.
  * Tự động kiểm tra HTTP (RFC 9110), DNS (RFC 1035) và SSL/TLS (RFC 5280).
  * Đối soát với `baseline` đang active của từng website.
  * Lưu kết quả quét vào bảng `monitoring_logs` trong CSDL `data/monitoring.db`.
  * Tự động kích hoạt chính sách dọn log cũ (`purge_old_logs(30)`).
* **Các hàm điều khiển:** `start_background_scheduler()`, `stop_background_scheduler()`, `resume_background_scheduler()`, `update_scheduler_interval()`, `run_monitors_now()`, `get_scheduler_info()`.

#### 3. Tích hợp Giao diện điều khiển tại Sidebar: [main.py]
* **Khởi chạy nền an toàn:** Dùng `@st.cache_resource` để đảm bảo scheduler chỉ khởi tạo 1 lần duy nhất trong toàn bộ vòng đời ứng dụng, không bị trùng lặp tác vụ khi người dùng tương tác với Streamlit.
* **Bảng điều khiển trực quan tại Sidebar:**
  * **Trạng thái:** 🟢 Đang Chạy Tự Động / 🔴 Đang Tạm Dừng.
  * **Thời gian:** Hiển thị thời điểm lần quét kế tiếp và số lần quét đã thực hiện.
  * **Thanh trượt điều chỉnh chu kỳ quét:** Tùy chọn tần suất quét (`30s`, `60s`, `2 phút`, `5 phút`, `10 phút`).
  * **Nút bấm thao tác nhanh:**
    * ⏸️ **Tạm dừng** / ▶️ **Tiếp tục**.
    * ⚡ **Quét ngay tất cả:** Kích hoạt quét toàn bộ website ngay lập tức ngoài chu kỳ.

---

### 🚀 Trải nghiệm trên Streamlit Dashboard
Ứng dụng đang chạy tại **http://localhost:8501**:
1. Scheduler sẽ tự động quét ngầm mỗi 60 giây và ghi nhật ký vào CSDL.
2. Bạn có thể chuyển qua tab **"📈 Lịch sử & Xu hướng"** để theo dõi số lượng bản ghi và biểu đồ độ trễ tăng dần tự động theo thời gian thực.
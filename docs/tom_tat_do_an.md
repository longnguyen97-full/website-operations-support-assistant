
# Tóm tắt Đồ án Tốt nghiệp: Hệ thống Agentic AI hỗ trợ giám sát, phân tích và cảnh báo sự cố website

## 1. Thông tin chung
*   **Tên đề tài:** Nghiên cứu và xây dựng hệ thống Agentic AI hỗ trợ giám sát đa tín hiệu, phân tích và cảnh báo sự cố website.
*   **Tên tiếng Anh:** Research and Development of an Agentic AI System for Multi-Signal Website Monitoring, Incident Analysis, and Alerting.

## 2. Bối cảnh và Tính cấp thiết
Việc giám sát website thủ công hoặc chỉ dựa vào các ngưỡng (threshold) rời rạc hiện nay gặp nhiều hạn chế:
*   Thiếu ngữ cảnh, cảnh báo rời rạc.
*   Khó phân biệt lỗi tạm thời với sự cố nghiêm trọng.
*   Thiếu khả năng tự động tóm tắt nguyên nhân, phạm vi ảnh hưởng và đề xuất hướng xử lý.
*   **Giải pháp:** Ứng dụng Agentic AI để chuyển từ mô hình "thu thập chỉ số và gửi cảnh báo" sang mô hình "phát hiện, tổng hợp bằng chứng, phân tích và hỗ trợ xử lý".

## 3. Mục tiêu
*   **Tổng quát:** Xây dựng hệ thống Agentic AI trợ lý vận hành (không thay thế hoàn toàn kỹ sư), có khả năng giám sát, tương quan sự kiện và hỗ trợ xử lý sự cố.
*   **Cụ thể:**
    *   Giám sát đa dạng tín hiệu: HTTP, DNS, SSL/TLS, hiệu năng, DOM/giao diện.
    *   Phát hiện bất thường và tương quan các tín hiệu liên quan.
    *   Sử dụng Agentic AI để lập kế hoạch, thu thập bằng chứng, đánh giá mức độ nghiêm trọng và sinh báo cáo bằng ngôn ngữ tự nhiên.
    *   Cảnh báo tức thời và gửi báo cáo tổng hợp hằng ngày.

## 4. Kiến trúc hệ thống
Hệ thống bao gồm các thành phần Agent chính:
1.  **Monitoring Orchestrator Agent:** Điều phối trung tâm, lập lịch và quản lý luồng xử lý.
2.  **Probe Agent:** Thu thập bằng chứng kỹ thuật.
3.  **Anomaly Detection Agent:** Phát hiện bất thường dựa trên luật hoặc thống kê.
4.  **Incident Correlation Agent:** Nhóm các cảnh báo liên quan thành một sự cố duy nhất.
5.  **Incident Analysis Agent:** Phân tích, tóm tắt và đưa ra khuyến nghị xử lý.
6.  **Reporting and Notification Agent:** Gửi cảnh báo/báo cáo.

## 5. Khả năng cốt lõi của Agentic AI
Hệ thống phải thể hiện 4 khả năng: **Lập kế hoạch** (planning), **Sử dụng công cụ** (tool use), **Phản hồi linh hoạt** (self-correction), và **Sử dụng bộ nhớ/tri thức** (memory & knowledge).

## 6. Phạm vi thực hiện
*   **Bắt buộc:** Giám sát HTTP, DNS, SSL/TLS, hiệu năng (response time), kiểm tra DOM/giao diện cơ bản.
*   **Không bao gồm (hướng mở rộng):** Tự động sửa mã nguồn, tự động thay đổi cấu hình hạ tầng (DNS/Firewall), phân tích log quy mô lớn.

## 7. Phương pháp đánh giá
*   **Kịch bản:** Tạo lỗi chủ động (dừng server, lỗi 500, lỗi DNS, sai chứng chỉ, v.v.).
*   **Chỉ số:** Precision, Recall, F1-score, Mean Time to Detect (MTTD), chất lượng báo cáo (rubric), hiệu quả giảm cảnh báo trùng lặp.
*   **Đối chứng:** So sánh giữa cảnh báo truyền thống, giám sát đa tín hiệu (không AI) và hệ thống Agentic AI đầy đủ.

## 8. Công nghệ đề xuất
*   **Backend:** Python, FastAPI.
*   **Dữ liệu:** PostgreSQL/TimescaleDB.
*   **Công cụ:** Playwright (giao diện), HTTPX (HTTP), dnspython (DNS), LangGraph (Agent orchestration).

### 📊 Bảng Phân Định Bản Chất 6 Tác Tử

| STT | Tác Tử (Agent Name) | Phân Loại Xử Lý | Có Cần Gọi LLM Không? | Cơ Chế Hoạt Động Cốt Lõi |
| :---: | :--- | :---: | :---: | :--- |
| **1** | **Probe Agent** | **Execution / Tooling** | ❌ **Không** | Thực thi trực tiếp các thư viện mạng (`httpx`, `dnspython`, `ssl`, `playwright`). |
| **2** | **Anomaly Detection Agent** | **Rule-Based & Statistical** | ❌ **Không** | Tính toán công thức thống kê Z-Score ($Z = \frac{X - \mu}{\sigma}$) và so khớp bộ luật tiêu chuẩn RFC 9110/1035/5280. |
| **3** | **Incident Correlation Agent** | **Rule-Based (Graph Tree)** | ❌ **Không** | Duyệt cây phụ thuộc hạ tầng mạng (*DNS ➔ TCP ➔ SSL ➔ HTTP ➔ DOM*) để triệt tiêu cảnh báo rác (*Noise Reduction*). |
| **4** | **Incident Analysis Agent** | **LLM-Powered Reasoning** |  **BẮT BUỘC / CHÍNH YẾU** | **Gọi LLM (Gemini / Claude)** kết hợp RAG/Knowledge Base để sinh bản tóm tắt nguyên nhân gốc (RCA), đánh giá tác động và đề xuất Runbook bằng ngôn ngữ tự nhiên. |
| **5** | **Reporting & Notification Agent** | **Execution / Dispatching** | ❌ **Không** | Render template HTML/Markdown và gửi email qua giao thức SMTP. |
| **6** | **Monitoring Orchestrator Agent** | **Execution & State Machine** | ⚠️ **Tùy chọn (Hybrid)** | Đóng vai trò State Machine điều phối luồng (Planning, Re-probe). Chạy bằng code tất định để đạt độ trễ <100ms, có thể gọi LLM khi cần lập kế hoạch cho các tình huống bất định phức tạp. |

---

### 🔍 Tổng Kết Phân Loại:

1. **Cần gọi LLM (1 Agent)**:
   * **`Incident Analysis Agent`**: Đây là bộ não suy luận duy nhất cần đến khả năng sinh ngôn ngữ tự nhiên, phân tích ngữ cảnh sự cố đa chiều và tư vấn phương án kỹ thuật như một kỹ sư SRE cấp cao.
2. **Xử lý Luật & Thống kê (2 Agents)**:
   * **`Anomaly Detection Agent`** & **`Incident Correlation Agent`**: Sử dụng toán học thuần túy và cây quyết định tất định để phát hiện bất thường và khử nhiễu nhanh, chính xác 100%.
3. **Thuần Thực thi & Điều động công cụ (3 Agents)**:
   * **`Probe Agent`**, **`Reporting and Notification Agent`**, **`Monitoring Orchestrator Agent`**: Thực hiện các thao tác I/O mạng, lập lịch, gọi tool và gửi thông báo.

---

### 💡 Giá Trị Học Thuật & Lý Do Thiết Kế Cho Thuyết Minh Đồ Án:

1. **Không lạm dụng LLM (Cost & Latency Efficiency)**:
   * Nếu để LLM đi đọc từng chỉ số ping mili-giây, hệ thống sẽ mất 3–5 giây và tốn phí token cho mỗi chu kỳ quét 60 giây. Việc đưa tầng Probe và Anomaly về Rule/Math giúp toàn bộ chu trình quét phản hồi gần như tức thì (<300ms).
2. **Triệt tiêu ảo giác số liệu (Zero Hallucination)**:
   * Các con số kỹ thuật (HTTP Status, Latency ms, Expired Days, Z-Score) được tính toán bằng Python chuẩn xác 100%, LLM chỉ tiếp nhận kết quả đã được lọc sạch để làm nhiệm vụ diễn giải ngữ nghĩa.
3. **Mô hình Hybrid Agentic AI chuẩn công nghiệp**:
   * Sự kết hợp giữa **Tác tử thực thi tất định (Deterministic Execution)** và **Tác tử suy luận xác suất (Probabilistic LLM Reasoning)** là xu hướng kiến trúc tối ưu nhất hiện nay trong vận hành hệ thống (AIOps).
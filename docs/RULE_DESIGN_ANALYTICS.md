# RULE_DESIGN_ANALYTICS.md

Quy định kỹ thuật và nguyên tắc thiết kế module phân tích dữ liệu giám sát, phát hiện bất thường và tương quan sự cố (Analytics Engine) cho hệ thống Website Operations Support Assistant.

---

## 1. Mục tiêu và Vai trò của Module Analytics

Module Analytics đóng vai trò là tầng trung gian xử lý dữ liệu giữa **Probe Agents (Thu thập tín hiệu kỹ thuật)** và **Reporting/Agentic AI Layer (Suy luận và Cảnh báo)**.

Nhiệm vụ chính:
1. **Phát hiện bất thường đa tầng**: Kết hợp giữa **Luật logic kỹ thuật (Rule-based)** và **Thống kê chuỗi thời gian (Z-Score)**.
2. **Tương quan sự cố & Khử nhiễu (Noise Reduction)**: Gom nhóm các cảnh báo phụ thuộc đa tín hiệu về một nguyên nhân gốc (Root Cause) duy nhất để tránh bão cảnh báo (Alert Fatigue).
3. **Chuẩn hóa điểm rủi ro (Anomaly Scoring)**: Tính toán điểm bất thường tổng hợp từ 0 đến 100 điểm.
4. **Phục vụ đánh giá đối chứng (Benchmark Evaluation)**: Cung cấp 2 cấu hình vận hành để so sánh hiệu năng khoa học trong đồ án tốt nghiệp.

---

## 2. Quy tắc Phân tích Thống kê Chuỗi Thời gian (Z-Score Analysis)

### 2.1. Công thức và Cơ chế Tính toán
Thuật toán Z-Score (Standard Score) đo lường độ lệch chuẩn của giá trị độ trễ hiện tại $X$ (`response_time_ms`) so với phân phối lịch sử $N$ lần quét gần nhất:

$$Z = \frac{X - \mu}{\sigma}$$

Trong đó:
* $X$: Thời gian phản hồi của lần quét hiện tại.
* $\mu$ (Mean): Độ trễ trung bình của $N$ mẫu lịch sử gần nhất (mặc định lấy từ bảng `monitoring_logs`, $N \ge 5$).
* $\sigma$ (Sample Standard Deviation): Độ lệch chuẩn mẫu:
  $$\sigma = \sqrt{\frac{1}{N - 1} \sum_{i=1}^{N} (X_i - \mu)^2}$$

### 2.2. Quy tắc Phân loại Ngưỡng Z-Score
* **$|Z| < 2.5$ (`HEALTHY`)**: Độ trễ biến thiên bình thường trong dải phương sai thống kê cho phép.
* **$2.5 \le |Z| < 3.5$ (`WARNING`)**: Độ trễ tăng cao đáng chú ý so với mức trung bình lịch sử.
* **$|Z| \ge 3.5$ (`CRITICAL`)**: Phát hiện đột biến độ trễ nghiêm trọng (**Latency Spike**), kích hoạt cảnh báo sự cố hiệu năng.

### 2.3. Xử lý Trường hợp Biên (Edge Cases)
* **Số lượng mẫu $N < 5$**: Không kích hoạt cảnh báo thống kê Z-Score (chỉ dựa vào ngưỡng luật) để tránh cảnh báo giả khi chưa đủ dữ liệu nền tảng (Cold Start).
* **Độ lệch chuẩn $\sigma = 0$** (tất cả các mẫu lịch sử bằng nhau): Nếu chênh lệch tuyệt đối $|X - \mu| > 500\text{ms}$ thì gán $Z = 99.0$ (Spike), ngược lại gán $Z = 0.0$.

---

## 3. Quy tắc Đánh giá theo Luật (Rule-Based Engine)

Bộ luật kiểm tra sự vi phạm trên từng tín hiệu giám sát kỹ thuật:

### 3.1. Tầng HTTP (RFC 9110)
* **`HTTP_CONN_FAILED` (CRITICAL)**: Không thể kết nối hoặc request bị timeout (Trọng số weight = 40).
* **`HTTP_5XX_SERVER_ERROR` (CRITICAL)**: Mã phản hồi $500 \le \text{Status} \le 599$ (weight = 35).
* **`HTTP_4XX_CLIENT_ERROR` (WARNING)**: Mã phản hồi $400 \le \text{Status} \le 499$ không nằm trong expected status (weight = 20).
* **`HTTP_STATUS_MISMATCH` (WARNING)**: Mã HTTP khác mã kỳ vọng (weight = 15).
* **`HTTP_EXCESSIVE_REDIRECTS` (WARNING)**: Chuỗi chuyển hướng $> 4$ bước (weight = 10).

### 3.2. Tầng DNS (RFC 1035)
* **`DNS_RESOLUTION_FAILED` (CRITICAL)**: Tên miền không thể phân giải (`NXDOMAIN`, `TIMEOUT`) (weight = 40).
* **`DNS_UNEXPECTED_DRIFT` (WARNING)**: Bản ghi IP/CNAME thay đổi ngoài dự kiến so với baseline chuẩn và không khớp với danh sách IP của CDN/Load Balancer (weight = 20).

### 3.3. Tầng SSL/TLS (RFC 5280 & RFC 8446)
* **`SSL_CERTIFICATE_EXPIRED` (CRITICAL)**: Chứng chỉ đã hết hạn sử dụng (weight = 35).
* **`SSL_HOSTNAME_MISMATCH` (CRITICAL)**: Tên miền không khớp với Common Name (CN) hoặc Subject Alternative Names (SANs) (weight = 30).
* **`SSL_UNTRUSTED_CA` (CRITICAL)**: Chứng chỉ tự ký (Self-signed) hoặc thiếu Intermediate CA trong chuỗi (weight = 25).
* **`SSL_EXPIRING_SOON` (WARNING)**: Số ngày còn lại $\le 14$ ngày (weight = 15).

### 3.4. Tầng Hiệu năng SRE & Giao diện (DOM / Visual)
* **`PERF_CRITICAL_LATENCY` (CRITICAL)**: Response time $\ge 5000\text{ms}$ (weight = 30).
* **`PERF_DEGRADED_LATENCY` (WARNING)**: Response time $\ge 2000\text{ms}$ (weight = 15).
* **`DOM_STRUCTURAL_CORRUPTION` (CRITICAL/WARNING)**: Trang rỗng hoặc thiếu thẻ cốt lõi `<title>`, `<h1>` (weight = 25).
* **`VISUAL_REGRESSION_DETECTED` (CRITICAL/WARNING)**: Tỷ lệ lệch pixel so với baseline $> 3.0\%$ (weight = 25).

---

## 4. Quy tắc Tương quan Sự cố & Khử nhiễu (Correlation & Noise Reduction)

Áp dụng cây phụ thuộc tầng mạng từ thấp đến cao (Layered Dependency Tree) để xác định **Nguyên nhân Gốc (Root Cause)** và **Triệt tiêu các cảnh báo phụ thuộc**:

```
[L3/L4: DNS Resolution] ──► [L4: TCP Socket Connect] ──► [L6: SSL Handshake] ──► [L7: HTTP App] ──► [Client: DOM / Visual]
```

### Luật Tương quan Cụ thể:
1. **Nếu lỗi DNS (`DNS_RESOLUTION_FAILED`)**:
   * Nguyên nhân gốc: `DNS_RESOLUTION_OUTAGE`.
   * Hành động khử nhiễu: Triệt tiêu toàn bộ cảnh báo lỗi kết nối HTTP và lỗi bắt tay SSL phía sau.
2. **Nếu lỗi kết nối TCP (`Connection Refused` / `10061`)**:
   * Nguyên nhân gốc: `SERVER_PROCESS_DOWN` (Web server/Port bị đóng).
   * Hành động khử nhiễu: Triệt tiêu cảnh báo lỗi chứng chỉ SSL.
3. **Nếu lỗi chứng chỉ SSL hết hạn (`SSL_CERTIFICATE_EXPIRED`)**:
   * Nguyên nhân gốc: `SSL_CERT_EXPIRED`.
   * Hành động khử nhiễu: Gom nhóm toàn bộ cảnh báo bảo mật về 1 sự cố duy nhất.
4. **Nếu lỗi HTTP 5xx Server Error**:
   * Nguyên nhân gốc: `BACKEND_APPLICATION_ERROR`.

---

## 5. Quy tắc Phân định 2 Cấu hình Đối chứng trong Đồ án

| Đặc điểm thiết kế | Cấu hình 1: Ngưỡng truyền thống (`THRESHOLD_BASED`) | Cấu hình 2: Đa tín hiệu + Luật + Z-Score (`MULTI_SIGNAL_RULE_STATISTICAL`) |
| :--- | :--- | :--- |
| **Phạm vi giám sát** | Đơn tín hiệu (chỉ xét HTTP Status và Latency) | Hợp nhất 6 tín hiệu (HTTP, DNS, SSL, SRE, DOM, Visual) |
| **Phát hiện bất thường** | So khớp ngưỡng cứng tĩnh (Threshold) | **Bộ luật tiêu chuẩn RFC** + **Z-Score chuỗi thời gian** |
| **Khử nhiễu cảnh báo** | ❌ Không có (Sinh nhiều cảnh báo rời rạc) | ✅ **Có** (Triệt tiêu cảnh báo rác, tính tỷ lệ Noise Reduction %) |
| **Xác định nguyên nhân** | ❌ Không xác định được | ✅ **Tự động gom nhóm Root Cause** |
| **Điểm rủi ro (Score)** | ❌ Không hỗ trợ | ✅ Có (**Anomaly Score 0 - 100 điểm**) |
| **Sử dụng AI / LLM** | ❌ Không | ❌ Không *(Đóng vai trò baseline đối chứng với Mức 3: Agentic AI)* |

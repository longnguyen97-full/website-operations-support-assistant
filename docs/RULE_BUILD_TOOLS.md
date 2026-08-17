# RULE_BUILD_TOOLS.md

Quy định kỹ thuật và tiêu chuẩn thiết kế các công cụ giám sát hệ thống website dựa trên các chuẩn RFC quốc tế.

## 1. HTTP Monitoring

* Dựa trên **RFC 9110** để định nghĩa ngữ nghĩa của HTTP, các phương thức, trường header và các nhóm mã trạng thái 1xx, 2xx, 3xx, 4xx và 5xx.
* Công cụ phải xác định được các yếu tố: mã trạng thái thành công, redirect và redirect chain, lỗi phía client và phía server, phương thức GET hoặc HEAD, cũng như các header liên quan đến caching, retry và server response.
* Mỗi endpoint cần có `expected status code` riêng, bởi không phải mọi mã 4xx hoặc 5xx đều là sự cố (ví dụ: HTTP 404 có thể là kết quả hợp lệ đối với một URL đã biết là không tồn tại).

## 2. DNS Monitoring

* Dựa trên **RFC 1035** để triển khai và đặc tả hệ thống tên miền DNS.
* Công cụ phải kiểm tra được:
* Khả năng phân giải tên miền.
* Bản ghi A và AAAA.
* CNAME.
* MX hoặc TXT nếu thuộc yêu cầu hệ thống.
* Thời gian phân giải.
* Thay đổi giá trị bản ghi so với baseline.


* Hệ thống phải có cơ chế phân biệt giữa thay đổi DNS ngoài dự kiến với thay đổi có kế hoạch hoặc do cơ chế load balancing.

## 3. SSL/TLS Monitoring

* Dựa trên **RFC 5280** (hồ sơ chứng chỉ X.509 và cơ chế xác thực đường dẫn chứng chỉ) và **RFC 8446** (giao thức TLS 1.3).
* Các thuộc tính bắt buộc phải kiểm tra gồm:
* Thời điểm bắt đầu và hết hạn chứng chỉ.
* Subject Alternative Name (SAN).
* Hostname validation.
* Certificate chain.
* Certificate issuer.
* Phát hiện chứng chỉ tự ký hoặc không được tin cậy.
* Phiên bản TLS được hỗ trợ.


* Không được chỉ dựa vào số ngày còn lại của chứng chỉ; một chứng chỉ còn hạn nhưng sai hostname hoặc có certificate chain không hợp lệ vẫn phải được phân loại là sự cố.
"""
Website Operations Support Assistant - Tools Package
Tập hợp 6 công cụ giám sát hệ thống website theo chuẩn RULE_BUILD_TOOLS.md:
1. http_checker: Kiểm tra HTTP theo RFC 9110 (Mã trạng thái, redirect chain, cache headers, latency).
2. dns_checker: Kiểm tra DNS theo RFC 1035 (A, AAAA, CNAME, MX, TXT, TTL, Load balancing, Baseline).
3. ssl_checker: Kiểm tra SSL/TLS theo RFC 5280 & RFC 8446 (SAN, Hostname, Issuer, Hạn dùng, Self-signed, CA).
4. performance_checker: Giám sát hiệu năng SRE & Synthetic Monitoring (TTFB, Load time, Phân rã thời gian, Baseline so sánh).
5. dom_validator: Kiểm tra cấu trúc DOM Structural Monitoring (Title, Headings, Nav, Forms, Buttons/CTA, Selectors).
6. visual_checker: Giám sát chênh lệch giao diện Playwright Visual Regression (Masking động, Pixel Diff, Heatmap Diff).
"""

from tools.http_checker import check_http, get_status_category
from tools.dns_checker import check_dns
from tools.ssl_checker import check_ssl
from tools.performance_checker import check_performance
from tools.dom_validator import validate_dom
from tools.visual_checker import check_visual_regression

__all__ = [
    "check_http",
    "get_status_category",
    "check_dns",
    "check_ssl",
    "check_performance",
    "validate_dom",
    "check_visual_regression"
]

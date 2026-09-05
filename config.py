"""
Centralized Configuration & Fallback Defaults for Website Operations Support Assistant.
Nạp biến môi trường từ file .env (nếu có) và cung cấp giá trị mặc định (Fallback).
"""

import os
from pathlib import Path
from datetime import timezone, timedelta
from dotenv import load_dotenv

# Tự động nạp file .env từ thư mục gốc
BASE_DIR = Path(__file__).resolve().parent
ENV_FILE = BASE_DIR / ".env"
if ENV_FILE.exists():
    load_dotenv(dotenv_path=ENV_FILE)
else:
    load_dotenv()

# ==================== 1. MÚI GIỜ & ĐỊNH DẠNG THỜI GIAN ====================
TIMEZONE_OFFSET_HOURS = int(os.getenv("TIMEZONE_OFFSET_HOURS", 7))
TIMEZONE_NAME = os.getenv("TIMEZONE_NAME", "Asia/Ho_Chi_Minh")
TZ_VN = timezone(timedelta(hours=TIMEZONE_OFFSET_HOURS))

# ==================== 2. CƠ SỞ DỮ LIỆU & LƯU TRỮ ====================
DATA_DIR = BASE_DIR / os.getenv("DATA_DIR", "data")
DB_FILE_NAME = os.getenv("DB_FILE_NAME", "monitoring.db")
DB_PATH = DATA_DIR / DB_FILE_NAME

# Chính sách lưu trữ dữ liệu (Data Retention Policy)
DATA_RETENTION_DAYS = int(os.getenv("DATA_RETENTION_DAYS", 30))

# Đường dẫn file danh mục website ban đầu (Initial seed)
TARGET_WEBSITES_FILE = BASE_DIR / os.getenv("TARGET_WEBSITES_FILE", "target_websites.json")

# ==================== 3. BỘ LẬP LỊCH (APSCHEDULER) ====================
DEFAULT_SCHEDULER_INTERVAL_SECONDS = int(os.getenv("SCHEDULER_INTERVAL_SECONDS", 14400))  # 4 tiếng
MIN_SCHEDULER_INTERVAL_SECONDS = 10
MAX_SCHEDULER_INTERVAL_SECONDS = 86400  # 24 tiếng

# ==================== 4. CẤU HÌNH EMAIL & BÁO CÁO (FALLBACK) ====================
DEFAULT_SMTP_SERVER = os.getenv("SMTP_SERVER", "smtp.gmail.com")
DEFAULT_SMTP_PORT = int(os.getenv("SMTP_PORT", 587))
DEFAULT_SENDER_EMAIL = os.getenv("SENDER_EMAIL", "")
DEFAULT_SENDER_PASSWORD = os.getenv("SENDER_PASSWORD", "")
DEFAULT_RECIPIENT_EMAILS = os.getenv("RECIPIENT_EMAILS", "")
DEFAULT_USE_TLS = os.getenv("USE_TLS", "true").lower() in ("true", "1", "yes")

# Cờ bật tắt thông báo mặc định
DEFAULT_EMAIL_ENABLED = os.getenv("EMAIL_ENABLED", "false").lower() in ("true", "1", "yes")
DEFAULT_NOTIFY_CRITICAL = os.getenv("NOTIFY_CRITICAL", "true").lower() in ("true", "1", "yes")
DEFAULT_NOTIFY_WARNING = os.getenv("NOTIFY_WARNING", "true").lower() in ("true", "1", "yes")
DEFAULT_NOTIFY_RECOVERY = os.getenv("NOTIFY_RECOVERY", "true").lower() in ("true", "1", "yes")
DEFAULT_COOLDOWN_MINUTES = int(os.getenv("COOLDOWN_MINUTES", 15))

# Cấu hình Báo cáo Định kỳ Hàng ngày (Daily Health Digest)
DEFAULT_ENABLE_DAILY_REPORT = os.getenv("ENABLE_DAILY_REPORT", "false").lower() in ("true", "1", "yes")
DEFAULT_DAILY_REPORT_TIME = os.getenv("DAILY_REPORT_TIME", "08:00")

# ==================== 5. THAM SỐ PROBES & KIỂM TRA MẠNG ====================
HTTP_TIMEOUT_SECONDS = float(os.getenv("HTTP_TIMEOUT_SECONDS", 10.0))
DNS_TIMEOUT_SECONDS = float(os.getenv("DNS_TIMEOUT_SECONDS", 5.0))
SSL_TIMEOUT_SECONDS = float(os.getenv("SSL_TIMEOUT_SECONDS", 10.0))
PERFORMANCE_TIMEOUT_SECONDS = float(os.getenv("PERFORMANCE_TIMEOUT_SECONDS", 15.0))
DOM_TIMEOUT_SECONDS = float(os.getenv("DOM_TIMEOUT_SECONDS", 15.0))
VISUAL_TIMEOUT_SECONDS = float(os.getenv("VISUAL_TIMEOUT_SECONDS", 20.0))

# Ngưỡng cảnh báo chứng chỉ SSL sắp hết hạn (ngày)
SSL_EXPIRY_WARNING_DAYS = int(os.getenv("SSL_EXPIRY_WARNING_DAYS", 14))

# Ngưỡng cảnh báo hiệu năng SRE (ms)
PERFORMANCE_WARNING_THRESHOLD_MS = float(os.getenv("PERFORMANCE_WARNING_THRESHOLD_MS", 2000.0))
PERFORMANCE_CRITICAL_THRESHOLD_MS = float(os.getenv("PERFORMANCE_CRITICAL_THRESHOLD_MS", 5000.0))

# Ngưỡng phát hiện biến dạng giao diện (%)
VISUAL_DIFF_THRESHOLD_PERCENT = float(os.getenv("VISUAL_DIFF_THRESHOLD_PERCENT", 3.0))

# User-Agent mặc định cho HTTP & Browser Probes
DEFAULT_USER_AGENT = os.getenv("USER_AGENT", "WebsiteOperationsSupportAssistant/1.0")

# ==================== 6. CẤU HÌNH AI & MÔ HÌNH NGÔN NGỮ LỚN (GEMINI LLM) ====================
DEFAULT_GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "") or os.getenv("GOOGLE_API_KEY", "")
DEFAULT_GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")
DEFAULT_LLM_ENABLED = os.getenv("LLM_ENABLED", "false").lower() in ("true", "1", "yes")

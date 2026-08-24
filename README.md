# Website Operations Support Assistant

## Structure
```
website-operations-support-assistant/
├── .venv/
├── data/
│   ├── monitoring.db
│   ├── screenshots/          # Lưu trữ ảnh chụp màn hình Playwright
│   ├── visual_baselines/     # Lưu trữ ảnh baseline chuẩn đối chiếu
│   └── visual_diffs/         # Lưu trữ ảnh diff đánh dấu biến dạng giao diện
├── database/
│   ├── __init__.py
│   ├── db.py
│   └── repository.py
├── docs/
│   ├── FEATURE-DATABASE.md
│   ├── FEATURE-EMAIL-NOTIFICATION.md
│   ├── FEATURE-SCHEDULER.md
│   ├── RULE_BUILD_TOOLS.md
│   ├── RULE_DESIGN_DB.md
│   └── db-diagram.png
├── notifications/
│   ├── __init__.py
│   └── email_service.py
├── pages/
│   └── configuration.py
├── scheduler/
│   ├── __init__.py
│   └── monitor_scheduler.py
├── tools/
│   ├── __init__.py
│   ├── http_checker.py       # Kiểm tra HTTP theo RFC 9110
│   ├── dns_checker.py        # Kiểm tra DNS theo RFC 1035
│   ├── ssl_checker.py        # Kiểm tra SSL/TLS theo RFC 5280 / RFC 8446
│   ├── performance_checker.py# Giám sát hiệu năng SRE (TTFB, Load time)
│   ├── dom_validator.py      # Kiểm tra cấu trúc DOM với Playwright
│   └── visual_checker.py     # Chụp ảnh màn hình & So sánh Visual Regression với Playwright
├── .env.example
├── config.py
├── main.py
├── pyproject.toml
├── README.md
├── target_websites.json
├── ui.py
└── uv.lock
```

## Install Playwright Browsers (nếu chưa cài)
```bash
uv run playwright install chromium
```

## Run the app
```bash
uv run streamlit run main.py
```
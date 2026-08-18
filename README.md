# Website Operations Support Assistant

## Structure
```
.website-operations-support-assistant/
├── .venv/
├── data/
│   └── monitoring.db
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
├── scheduler/
│   ├── __init__.py
│   └── monitor_scheduler.py
├── tools/
│   ├── dns_checker.py
│   ├── http_checker.py
│   └── ssl_checker.py
├── .env.example
├── config.py
├── main.py
├── pyproject.toml
├── README.md
├── target_websites.json
├── ui.py
└── uv.lock
```

## Run the app
```bash
uv run streamlit run main.py
```
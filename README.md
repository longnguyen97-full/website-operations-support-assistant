# website-operations-support-assistant

## Structure
```
.website-operations-support-assistant/
├── .venv/
├── docs/
│   └── RULE_BUILD_TOOLS.md
├── tools/
│   ├── dns_checker.py
│   ├── http_checker.py
│   └── ssl_checker.py
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
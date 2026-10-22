"""
Entrypoint alias for Streamlit dashboard.
Cho phep nguoi dung chay ca 2 lenh:
  - uv run streamlit run main.py
  - uv run streamlit run app.py
"""
import sys
from pathlib import Path

# Add directory to sys.path
BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

from main import main

if __name__ == "__main__":
    main()

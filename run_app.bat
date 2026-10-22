@echo off
title SRE Agentic System - Enterprise Website Operations Platform
echo =====================================================================
echo    KHOI CHAY HE THONG SRE AGENTIC SYSTEM (PRODUCTION LAUNCHER)
echo =====================================================================
cd /d "%~dp0"

echo.
echo [1/2] Kiem tra moi truong thuc thi...
where uv >nul 2>nul
if %errorlevel% neq 0 (
    echo [!] Khong tim thay 'uv'. Dang thu dung python truc tiep...
    python -m streamlit run main.py
) else (
    echo [✓] Da tim thay uv. Dang khoi chay Streamlit Web Dashboard...
    uv run streamlit run main.py || uv run python -m streamlit run main.py
)

pause

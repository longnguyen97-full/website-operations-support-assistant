FROM python:3.12-slim

LABEL maintainer="Nguyen Hoang Bao Long"
LABEL description="SRE Agentic System - Autonomous Website Monitoring & Incident Operations Platform"

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    STREAMLIT_SERVER_PORT=8501 \
    STREAMLIT_SERVER_ADDRESS=0.0.0.0 \
    STREAMLIT_SERVER_HEADLESS=true

WORKDIR /app

# Install system utilities and playwright dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    git \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install uv package manager
RUN pip install --no-cache-dir uv

# Copy dependency files
COPY pyproject.toml uv.lock ./

# Install project dependencies using uv
RUN uv pip install --system -r pyproject.toml

# Install Playwright browser binaries
RUN python -m playwright install --with-deps chromium

# Copy application source code
COPY . .

# Expose Streamlit default port
EXPOSE 8501

HEALTHCHECK --interval=20s --timeout=10s --start-period=10s --retries=3 \
  CMD curl -f http://localhost:8501/_stcore/health || exit 1

CMD ["streamlit", "run", "app.py"]

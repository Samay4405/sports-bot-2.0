# ═══════════════════════════════════════════════════════════════
# Sports Bot v2 — Multi-stage Dockerfile
# ═══════════════════════════════════════════════════════════════

FROM python:3.13-slim AS base

# System dependencies for browser-use (CDP needs Chromium)
RUN apt-get update && apt-get install -y --no-install-recommends \
    chromium \
    chromium-driver \
    fonts-liberation \
    libnss3 \
    libxss1 \
    libasound2 \
    libatk-bridge2.0-0 \
    libgtk-3-0 \
    libdrm2 \
    libgbm1 \
    && rm -rf /var/lib/apt/lists/*

# Set Chrome path for browser-use
ENV CHROME_PATH=/usr/bin/chromium
ENV CHROMIUM_FLAGS="--no-sandbox --disable-gpu --disable-dev-shm-usage"

WORKDIR /app

# ─── Dependencies ──────────────────────────────────────────────
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ─── Application ───────────────────────────────────────────────
COPY . .

# Create screenshots directory
RUN mkdir -p /app/screenshots

# Expose FastAPI port
EXPOSE 8000

# Run with uvicorn (single worker — scheduler must be singleton)
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]

# development / test / production share the same image; only the CMD changes.
FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    TZ=UTC

# WeasyPrint necesita pango/cairo; curl para el healthcheck; tini para senales.
RUN apt-get update && apt-get install -y --no-install-recommends \
        libpango-1.0-0 \
        libpangoft2-1.0-0 \
        libcairo2 \
        libgdk-pixbuf-2.0-0 \
        shared-mime-info \
        fonts-liberation \
        fonts-dejavu-core \
        curl \
        ffmpeg \
        tini \
        bash \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt constraints.txt ./
RUN python -m pip install --no-cache-dir --upgrade -c constraints.txt pip \
    && pip install --no-cache-dir -c constraints.txt -r requirements.txt

COPY . .

# Usuario no root con directorios de datos propios
RUN useradd --create-home --uid 10001 --shell /bin/bash appuser \
    && mkdir -p /data/uploads /data/exports /data/backups \
    && chown -R appuser:appuser /app /data
USER appuser

EXPOSE 8000

HEALTHCHECK --interval=15s --timeout=5s --start-period=40s --retries=10 \
    CMD curl -fsS http://localhost:8000/api/health || exit 1

ENTRYPOINT ["/usr/bin/tini", "--"]

# ── develop ──────────────────────────────────────────────────
FROM base AS develop
COPY requirements-dev.txt ./
RUN pip install --no-cache-dir -c constraints.txt -r requirements-dev.txt
ENV APP_ENV=development PYTHONPATH=/app
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]

# ── prod ─────────────────────────────────────────────────────
FROM base AS prod
ENV APP_ENV=production PYTHONPATH=/app
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips", "*", "--ws-max-size", "8192", "--ws-max-queue", "8"]

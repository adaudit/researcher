FROM python:3.11-slim AS base

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml .
RUN pip install --no-cache-dir ".[llm]"

COPY . .

# ── Development target ──────────────────────────────────────────────
FROM base AS dev
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]

# ── Production API target ───────────────────────────────────────────
FROM base AS api
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4", "--loop", "uvloop"]

# ── Celery worker target ───────────────────────────────────────────
FROM base AS worker
CMD ["celery", "-A", "app.orchestrator.engine", "worker", "--loglevel=info", "--concurrency=4", "-Q", "default,workflows,autonomous"]

# ── Celery Beat scheduler target ───────────────────────────────────
FROM base AS scheduler
CMD ["celery", "-A", "app.orchestrator.engine", "beat", "--loglevel=info"]

# ── Test target ─────────────────────────────────────────────────────
FROM base AS test
RUN pip install --no-cache-dir ".[dev]"
CMD ["pytest", "tests/", "-v", "--tb=short"]

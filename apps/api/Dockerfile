FROM ghcr.io/astral-sh/uv:0.12.23 AS uv

FROM python:3.12.15-slim-trixie AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    PATH=/opt/venv/bin:$PATH \
    LEGIVEL_OCR_DEVICE=cpu \
    LEGIVEL_OCR_MODEL_DIR=/opt/legivel/models

RUN apt-get update \
    && apt-get upgrade -y --no-install-recommends \
    && apt-get install -y --no-install-recommends libgomp1 libglib2.0-0 libgl1 fonts-dejavu-core tesseract-ocr tesseract-ocr-por \
    && rm -rf /var/lib/apt/lists/*

COPY --from=uv /uv /usr/local/bin/uv
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-install-project --extra cpu --extra tesseract
COPY . .
RUN uv sync --frozen --extra cpu --extra tesseract && python -m legivel.cli download-models

FROM base AS test
RUN uv sync --frozen --extra cpu --extra tesseract --extra dev
CMD ["sh", "-c", "ruff check . && pytest"]

FROM base AS runtime
RUN useradd --system --uid 10001 --home-dir /nonexistent --shell /usr/sbin/nologin legivel \
    && mkdir -p /data/storage && chown legivel /data/storage
USER legivel
ENV LEGIVEL_STORAGE_DIR=/data/storage
EXPOSE 8000
CMD ["sh", "-c", "alembic upgrade head && python -m legivel.cli reencrypt --if-needed && exec uvicorn legivel.main:create_app --factory --host 0.0.0.0 --port 8000 --proxy-headers --forwarded-allow-ips='*' --no-access-log"]

FROM node:22-alpine AS frontend

WORKDIR /frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
RUN npm run build

FROM python:3.12-slim AS app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK=True

RUN apt-get update && apt-get install -y --no-install-recommends libgomp1 libglib2.0-0 libgl1 fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY pyproject.toml ./
RUN mkdir app && touch app/__init__.py && pip install ".[ocr,dev]" && rm -rf app

COPY . .
RUN pip install --no-deps -e .
COPY --from=frontend /frontend/dist ./frontend/dist

RUN useradd --create-home --uid 1000 greenocr && mkdir -p data storage /home/greenocr/.paddlex \
    && chown -R greenocr /app /home/greenocr
USER greenocr

EXPOSE 8000
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:create_app --factory --host 0.0.0.0 --port 8000"]

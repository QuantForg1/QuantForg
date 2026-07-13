# QuantForg MT5 Gateway — Windows / Linux sidecar image
# Does NOT include MetaTrader5 terminal (install on Windows host separately).
FROM python:3.13-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    MT5_GATEWAY_HOST=0.0.0.0 \
    MT5_GATEWAY_PORT=8765

WORKDIR /app

RUN apt-get update \
    && apt-get install --no-install-recommends -y curl \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml poetry.lock* ./
COPY app ./app
COPY core ./core
COPY services ./services

RUN pip install --no-cache-dir poetry==1.8.5 \
    && poetry config virtualenvs.create false \
    && poetry install --only main --no-interaction \
    && pip install --no-cache-dir "uvicorn[standard]>=0.34"

EXPOSE 8765

HEALTHCHECK --interval=15s --timeout=5s --retries=3 \
  CMD curl -fsS "http://127.0.0.1:${MT5_GATEWAY_PORT}/health" || exit 1

CMD ["python", "-m", "services.mt5_gateway.main"]

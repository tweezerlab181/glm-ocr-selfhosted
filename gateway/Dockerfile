FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1

# System libs for pypdfium2 / pillow / paddle runtime.
RUN apt-get update && apt-get install -y --no-install-recommends \
        libgl1 libglib2.0-0 curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Gateway deps first (layer cache), then the heavy glmocr[selfhosted] (pulls
# PaddlePaddle CPU). Pin paddlepaddle to a known-good version during bring-up.
# Build context is the repo root (see compose.yaml: context: .).
COPY gateway/pyproject.toml /app/pyproject.toml
RUN pip install --upgrade pip && pip install -e .
RUN pip install "glmocr[selfhosted]"

COPY gateway/app /app/app
COPY config /app/config

RUN groupadd --system app && useradd --system --gid app --home-dir /app app \
    && mkdir -p /scratch /paddle-cache \
    && chown -R app:app /app /scratch /paddle-cache

USER app

EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=3s --retries=5 \
    CMD curl -fsS http://localhost:8080/health || exit 1

CMD ["uvicorn", "app.main:create_app", "--factory", \
     "--host", "0.0.0.0", "--port", "8080"]

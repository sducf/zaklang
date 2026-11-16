
FROM python:3.12-slim-bookworm AS builder

RUN apt-get update && apt-get install -y \
    --no-install-recommends \
    build-essential curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

ENV RUSTUP_HOME=/opt/rustup \
    CARGO_HOME=/opt/cargo \
    PATH=/opt/cargo/bin:$PATH

RUN curl --proto '=https' --tlsv1.2 -sSf \
    https://sh.rustup.rs | \
    sh -s -- -y --profile minimal

WORKDIR /app/backend

COPY backend/requirements.txt ./requirements.txt
COPY zakc/ /app/zakc/

RUN python -m pip wheel \
    --no-cache-dir \
    --wheel-dir /wheels \
    -r requirements.txt


FROM python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app:/app/backend

COPY --from=builder /wheels /wheels

RUN pip install --no-cache-dir --no-index \
    /wheels/*.whl \
    && rm -rf /wheels

WORKDIR /app

COPY backend/ /app/backend/
COPY zakbench/ /app/zakbench/
COPY sandbox/ /app/sandbox/
COPY spec/ /app/spec/

RUN python -c "import zakc; assert callable(zakc.zak_transpile)"

WORKDIR /app/backend

CMD ["sh", "-c", "exec uvicorn main:app --host 0.0.0.0 --port ${PORT:-8080}"]

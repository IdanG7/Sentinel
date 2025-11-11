# Sentinel InfraMind Adapter - Dockerfile
FROM python:3.11-slim AS builder

WORKDIR /build

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy and install local dependencies first
COPY libs/sentinel-common /build/libs/sentinel-common
RUN pip install --no-cache-dir /build/libs/sentinel-common

# Copy service files
COPY services/infra-adapter/pyproject.toml .
COPY services/infra-adapter/app/ ./app/

# Build the service wheel
RUN pip install --no-cache-dir build && \
    python -m build --wheel && \
    pip wheel --no-cache-dir --wheel-dir=/build/wheels -e .

FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /build/wheels /wheels
RUN pip install --no-cache-dir /wheels/*.whl && rm -rf /wheels

COPY services/infra-adapter/app/ /app/app/

RUN useradd -m -u 1000 sentinel && chown -R sentinel:sentinel /app
USER sentinel

EXPOSE 50051

CMD ["python", "-m", "app.main"]

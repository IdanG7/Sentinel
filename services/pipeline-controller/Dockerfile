# Sentinel Pipeline Controller - Dockerfile
FROM python:3.11-slim AS builder

WORKDIR /build

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy and install local dependencies first
COPY libs/sentinel-common /build/libs/sentinel-common
COPY libs/k8s-driver /build/libs/k8s-driver
COPY libs/policy-engine /build/libs/policy-engine
RUN pip install --no-cache-dir /build/libs/sentinel-common && \
    pip install --no-cache-dir /build/libs/k8s-driver && \
    pip install --no-cache-dir /build/libs/policy-engine

# Copy service files
COPY services/pipeline-controller/pyproject.toml .
COPY services/pipeline-controller/app/ ./app/

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

COPY services/pipeline-controller/app/ /app/app/

RUN useradd -m -u 1000 sentinel && chown -R sentinel:sentinel /app
USER sentinel

EXPOSE 8001

CMD ["python", "-m", "app.main"]

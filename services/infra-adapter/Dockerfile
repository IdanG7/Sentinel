# Sentinel InfraMind Adapter - Dockerfile
FROM python:3.11-slim AS builder

WORKDIR /build

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy and build local dependencies as wheels
COPY libs/sentinel-common /build/libs/sentinel-common
RUN pip install --no-cache-dir build && \
    cd /build/libs/sentinel-common && \
    python -m build --wheel && \
    mkdir -p /build/wheels && \
    cp dist/*.whl /build/wheels/

# Copy service files
COPY services/infra-adapter/pyproject.toml /build/
COPY services/infra-adapter/app/ /build/app/

# Install local dependencies and build the service wheel
WORKDIR /build
RUN pip install --no-cache-dir /build/wheels/sentinel_common-*.whl && \
    pip install --no-cache-dir grpcio>=1.59.0 grpcio-tools>=1.59.0 protobuf>=4.25.0 pydantic-settings>=2.1.0 prometheus-client>=0.19.0 aiokafka>=0.10.0 tenacity>=8.2.0 && \
    python -m build --wheel && \
    cp dist/*.whl /build/wheels/

FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /build/wheels /wheels
RUN pip install --no-cache-dir /wheels/sentinel_common-*.whl && \
    pip install --no-cache-dir /wheels/sentinel_infra_adapter-*.whl && \
    rm -rf /wheels

COPY services/infra-adapter/app/ /app/app/

RUN useradd -m -u 1000 sentinel && chown -R sentinel:sentinel /app
USER sentinel

EXPOSE 50051

CMD ["python", "-m", "app.main"]

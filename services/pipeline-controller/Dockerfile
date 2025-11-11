# Sentinel Pipeline Controller - Dockerfile
FROM python:3.11-slim AS builder

WORKDIR /build

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy and build local dependencies as wheels
COPY libs/sentinel-common /build/libs/sentinel-common
COPY libs/k8s-driver /build/libs/k8s-driver
COPY libs/policy-engine /build/libs/policy-engine
RUN pip install --no-cache-dir build && \
    cd /build/libs/sentinel-common && python -m build --wheel && \
    mkdir -p /build/wheels && cp dist/*.whl /build/wheels/ && \
    cd /build/libs/k8s-driver && python -m build --wheel && \
    cp dist/*.whl /build/wheels/ && \
    cd /build/libs/policy-engine && python -m build --wheel && \
    cp dist/*.whl /build/wheels/

# Copy service files
COPY services/pipeline-controller/pyproject.toml /build/
COPY services/pipeline-controller/app/ /build/app/

# Install local dependencies and build the service wheel
WORKDIR /build
RUN pip install --no-cache-dir /build/wheels/sentinel_common-*.whl && \
    pip install --no-cache-dir /build/wheels/sentinel_k8s_driver-*.whl && \
    pip install --no-cache-dir /build/wheels/sentinel_policy_engine-*.whl && \
    python -m build --wheel && \
    cp dist/*.whl /build/wheels/

FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /build/wheels /wheels
RUN pip install --no-cache-dir /wheels/sentinel_common-*.whl && \
    pip install --no-cache-dir /wheels/sentinel_k8s_driver-*.whl && \
    pip install --no-cache-dir /wheels/sentinel_policy_engine-*.whl && \
    pip install --no-cache-dir /wheels/sentinel_pipeline_controller-*.whl && \
    rm -rf /wheels

COPY services/pipeline-controller/app/ /app/app/

RUN useradd -m -u 1000 sentinel && chown -R sentinel:sentinel /app
USER sentinel

EXPOSE 8001

CMD ["python", "-m", "app.main"]

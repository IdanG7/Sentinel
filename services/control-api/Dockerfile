# Sentinel Control API - Dockerfile
FROM python:3.11-slim AS builder

WORKDIR /build

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy and build local dependencies as wheels
COPY libs/sentinel-common /build/libs/sentinel-common
COPY libs/k8s-driver /build/libs/k8s-driver
RUN pip install --no-cache-dir build && \
    cd /build/libs/sentinel-common && python -m build --wheel && \
    mkdir -p /build/wheels && cp dist/*.whl /build/wheels/ && \
    cd /build/libs/k8s-driver && python -m build --wheel && \
    cp dist/*.whl /build/wheels/

# Copy service files
COPY services/control-api/pyproject.toml /build/
COPY services/control-api/app/ /build/app/

# Install local dependencies and build the service wheel
WORKDIR /build
RUN pip install --no-cache-dir /build/wheels/sentinel_common-*.whl && \
    pip install --no-cache-dir /build/wheels/sentinel_k8s_driver-*.whl && \
    pip install --no-cache-dir fastapi>=0.104.0 uvicorn[standard]>=0.24.0 pydantic-settings>=2.1.0 python-jose[cryptography]>=3.3.0 passlib[bcrypt]>=1.7.4 python-multipart>=0.0.6 httpx>=0.25.0 sqlalchemy>=2.0.23 alembic>=1.12.0 asyncpg>=0.29.0 prometheus-client>=0.19.0 aiokafka>=0.10.0 hvac>=2.1.0 tenacity>=8.2.0 && \
    python -m build --wheel && \
    cp dist/*.whl /build/wheels/

# Final stage
FROM python:3.11-slim

WORKDIR /app

# Install runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy wheels and install
COPY --from=builder /build/wheels /wheels
RUN pip install --no-cache-dir /wheels/sentinel_common-*.whl && \
    pip install --no-cache-dir /wheels/sentinel_k8s_driver-*.whl && \
    pip install --no-cache-dir /wheels/sentinel_control_api-*.whl && \
    rm -rf /wheels

# Copy application code
COPY services/control-api/app/ /app/app/

# Create non-root user
RUN useradd -m -u 1000 sentinel && chown -R sentinel:sentinel /app
USER sentinel

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Expose port
EXPOSE 8000

# Run application
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

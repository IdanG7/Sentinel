"""Sentinel Control API - Main application entry point."""

from contextlib import asynccontextmanager
from datetime import datetime

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from prometheus_client import Counter, Histogram, make_asgi_app

from app.api.v1 import action_plans, auth, deployments, policies, workloads
from app.core.config import get_settings
from app.models.schemas import HealthResponse

settings = get_settings()

# Prometheus metrics
http_requests_total = Counter(
    "http_requests_total",
    "Total HTTP requests",
    ["method", "endpoint", "status"],
)

http_request_duration_seconds = Histogram(
    "http_request_duration_seconds",
    "HTTP request duration in seconds",
    ["method", "endpoint"],
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup and shutdown events."""
    # Startup
    print("🚀 Starting Sentinel Control API...")
    print(f"   Version: {settings.api_version}")
    print(f"   Environment: {'Development' if settings.debug else 'Production'}")
    print(f"   Database: {settings.database_url_str.split('@')[1] if '@' in settings.database_url_str else 'configured'}")
    print(f"   Kafka: {settings.kafka_bootstrap_servers}")

    # Initialize database
    from app.core.database import init_db
    await init_db()
    print("   ✓ Database initialized")

    # Initialize event publisher
    from app.core.events import init_event_publisher
    await init_event_publisher(settings)
    print("   ✓ Event publisher initialized")

    yield

    # Shutdown
    print("🛑 Shutting down Sentinel Control API...")
    from app.core.events import shutdown_event_publisher
    await shutdown_event_publisher()
    print("   ✓ Event publisher stopped")


app = FastAPI(
    title=settings.api_title,
    description="Autonomous AI Infrastructure Management API",
    version=settings.api_version,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=settings.cors_allow_credentials,
    allow_methods=settings.cors_allow_methods,
    allow_headers=settings.cors_allow_headers,
)

# Include routers
app.include_router(auth.router, prefix=settings.api_prefix)
app.include_router(workloads.router, prefix=settings.api_prefix)
app.include_router(deployments.router, prefix=settings.api_prefix)
app.include_router(policies.router, prefix=settings.api_prefix)
app.include_router(action_plans.router, prefix=settings.api_prefix)

# Mount Prometheus metrics
metrics_app = make_asgi_app()
app.mount("/metrics", metrics_app)


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "service": "sentinel-control-api",
        "version": settings.api_version,
        "status": "operational",
        "docs": "/docs",
        "metrics": "/metrics",
    }


@app.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    """Health check endpoint."""
    return HealthResponse(
        status="healthy",
        version=settings.api_version,
        timestamp=datetime.utcnow(),
    )


@app.get("/ready")
async def ready():
    """Readiness probe endpoint."""
    # TODO: Check database, Vault, Kafka connections
    return {"status": "ready"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
        log_level=settings.log_level.lower(),
    )

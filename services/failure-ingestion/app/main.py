"""Failure Ingestion Service - Main FastAPI application."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import get_settings
from .routes import github_router, gitlab_router

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

logger = logging.getLogger(__name__)

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan manager.

    Handles startup and shutdown tasks.
    """
    # Startup
    logger.info("🚀 Starting Failure Ingestion Service...")
    logger.info(f"Environment: {settings.environment}")
    logger.info(f"Service: {settings.service_name} v{settings.version}")
    logger.info("✓ Failure Ingestion Service ready")

    yield

    # Shutdown
    logger.info("🛑 Shutting down Failure Ingestion Service...")
    logger.info("✓ Failure Ingestion Service stopped")


# Create FastAPI app
app = FastAPI(
    title="Failure Ingestion Service",
    description="Receives CI/CD webhook events and creates agent tasks",
    version=settings.version,
    lifespan=lifespan,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routes
app.include_router(github_router, prefix="/webhooks/github")
app.include_router(gitlab_router, prefix="/webhooks/gitlab")


# Health check endpoints
@app.get("/health")
async def health_check():
    """Basic health check."""
    return {
        "status": "healthy",
        "service": settings.service_name,
        "version": settings.version,
    }


@app.get("/ready")
async def readiness_check():
    """Readiness check for Kubernetes."""
    return {
        "status": "ready",
        "service": settings.service_name,
    }


@app.get("/")
async def root():
    """Root endpoint with service info."""
    return {
        "service": settings.service_name,
        "version": settings.version,
        "description": "Failure Ingestion Service - CI/CD Webhook Receiver",
        "endpoints": {
            "health": "/health",
            "ready": "/ready",
            "docs": "/docs",
            "github_webhooks": "/webhooks/github",
            "gitlab_webhooks": "/webhooks/gitlab",
        },
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=settings.port,
        reload=settings.environment == "development",
        log_level=settings.log_level.lower(),
    )

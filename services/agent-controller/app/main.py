"""Agent Controller - Main FastAPI application."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import get_settings
from .database import close_db, init_db
from .routes import agents_router, tasks_router

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

    Handles:
    - Database initialization
    - Startup tasks
    - Shutdown cleanup
    """
    # Startup
    logger.info("🚀 Starting Agent Controller...")
    logger.info(f"Environment: {settings.environment}")
    logger.info(f"Service: {settings.service_name} v{settings.version}")

    # Initialize database
    await init_db()

    logger.info("✓ Agent Controller ready")

    yield

    # Shutdown
    logger.info("🛑 Shutting down Agent Controller...")
    await close_db()
    logger.info("✓ Agent Controller stopped")


# Create FastAPI app
app = FastAPI(
    title="Agent Controller",
    description="Orchestration service for autonomous AI agents in Sentinel platform",
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
app.include_router(agents_router, prefix="/api/v1")
app.include_router(tasks_router, prefix="/api/v1")


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
    # TODO: Check database and Redis connectivity
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
        "description": "Agent Controller - Autonomous AI Agent Orchestration",
        "endpoints": {
            "health": "/health",
            "ready": "/ready",
            "docs": "/docs",
            "agents": "/api/v1/agents",
            "tasks": "/api/v1/tasks",
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

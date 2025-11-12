"""API routes for Agent Controller."""

from .agents import router as agents_router
from .tasks import router as tasks_router

__all__ = [
    "agents_router",
    "tasks_router",
]

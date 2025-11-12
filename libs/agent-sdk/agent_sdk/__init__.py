"""Sentinel Agent SDK - Build autonomous AI agents for Sentinel platform."""

from .client import AgentClient
from .models import (
    AgentCapabilities,
    AgentConfig,
    AgentHeartbeat,
    AgentInfo,
    AgentTask,
    TaskResult,
    TaskUpdate,
)

__version__ = "0.1.0"

__all__ = [
    "AgentClient",
    "AgentCapabilities",
    "AgentConfig",
    "AgentInfo",
    "AgentTask",
    "TaskResult",
    "TaskUpdate",
    "AgentHeartbeat",
]

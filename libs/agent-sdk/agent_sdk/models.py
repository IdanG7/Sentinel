"""Agent SDK Models - Data models for agent communication."""

from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class AgentCapabilities(BaseModel):
    """Agent capabilities definition."""

    supported_tasks: List[str] = Field(
        ..., description="List of task types this agent can handle"
    )
    max_concurrent_tasks: int = Field(default=5, ge=1, le=50)
    supported_failure_types: Optional[List[str]] = None
    timeout_seconds: int = Field(default=600, ge=60, le=3600)


class AgentConfig(BaseModel):
    """Agent configuration."""

    description: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    poll_interval: int = Field(default=5, description="Task polling interval in seconds")
    heartbeat_interval: int = Field(default=30, description="Heartbeat interval in seconds")


class AgentInfo(BaseModel):
    """Agent registration information."""

    id: UUID
    name: str
    version: str
    description: Optional[str]
    capabilities: Dict[str, Any]
    status: str
    health_score: float
    created_at: datetime


class AgentTask(BaseModel):
    """Task assigned to agent."""

    id: UUID
    task_type: str
    context: Dict[str, Any]
    timeout_seconds: int = 600
    correlation_id: Optional[UUID] = None


class TaskUpdate(BaseModel):
    """Task progress update."""

    status: Optional[str] = None
    progress: Optional[float] = Field(None, ge=0.0, le=1.0)
    result: Optional[Dict[str, Any]] = None
    artifacts: Optional[List[Dict[str, Any]]] = None
    metrics: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None


class TaskResult(BaseModel):
    """Task execution result."""

    success: bool
    data: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None
    artifacts: Optional[List[Dict[str, Any]]] = None
    metrics: Optional[Dict[str, Any]] = None


class AgentHeartbeat(BaseModel):
    """Agent heartbeat data."""

    health_score: float = Field(..., ge=0.0, le=1.0)
    active_tasks: int = Field(default=0, ge=0)
    metrics: Dict[str, Any] = Field(default_factory=dict)

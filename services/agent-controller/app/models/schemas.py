"""Pydantic schemas for Agent Controller API."""

from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field


# Agent Schemas


class AgentCapabilities(BaseModel):
    """Agent capabilities."""

    supported_tasks: List[str] = Field(
        ..., description="List of task types this agent can handle"
    )
    max_concurrent_tasks: int = Field(default=5, ge=1, le=50)
    supported_failure_types: Optional[List[str]] = None
    timeout_seconds: int = Field(default=600, ge=60, le=3600)


class AgentCreate(BaseModel):
    """Schema for creating an agent."""

    name: str = Field(..., min_length=3, max_length=100)
    version: str = Field(..., pattern=r"^\d+\.\d+\.\d+$")
    description: Optional[str] = Field(None, max_length=500)
    capabilities: AgentCapabilities
    configuration: Dict[str, Any] = Field(default_factory=dict)


class AgentUpdate(BaseModel):
    """Schema for updating an agent."""

    version: Optional[str] = Field(None, pattern=r"^\d+\.\d+\.\d+$")
    description: Optional[str] = None
    capabilities: Optional[AgentCapabilities] = None
    configuration: Optional[Dict[str, Any]] = None
    status: Optional[str] = Field(None, pattern="^(active|paused|offline)$")


class AgentResponse(BaseModel):
    """Schema for agent response."""

    id: UUID
    name: str
    version: str
    description: Optional[str]
    capabilities: Dict[str, Any]
    configuration: Dict[str, Any]
    status: str
    health_score: float
    last_heartbeat: Optional[datetime]
    total_tasks: int
    successful_tasks: int
    failed_tasks: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class AgentHeartbeat(BaseModel):
    """Schema for agent heartbeat."""

    health_score: float = Field(..., ge=0.0, le=1.0)
    active_tasks: int = Field(default=0, ge=0)
    metrics: Dict[str, Any] = Field(default_factory=dict)


# Task Schemas


class AgentTaskCreate(BaseModel):
    """Schema for creating an agent task."""

    task_type: str = Field(..., min_length=3, max_length=50)
    context: Dict[str, Any] = Field(..., description="Task context and parameters")
    payload: Optional[str] = Field(None, description="Large data payload if needed")
    timeout_seconds: Optional[int] = Field(None, ge=60, le=3600)
    correlation_id: Optional[UUID] = Field(None, description="Link to InfraMind prediction")


class AgentTaskUpdate(BaseModel):
    """Schema for updating a task (from agent)."""

    status: Optional[str] = None
    progress: Optional[float] = Field(None, ge=0.0, le=1.0)
    result: Optional[Dict[str, Any]] = None
    artifacts: Optional[List[Dict[str, Any]]] = None
    metrics: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None


class AgentTaskResponse(BaseModel):
    """Schema for task response."""

    id: UUID
    agent_id: UUID
    agent_name: str
    task_type: str
    context: Dict[str, Any]
    status: str
    progress: float
    result: Optional[Dict[str, Any]]
    artifacts: Optional[List[Dict[str, Any]]]
    metrics: Optional[Dict[str, Any]]
    error_message: Optional[str]
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    duration_ms: Optional[int]
    retry_count: int
    correlation_id: Optional[UUID]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# Failure Fix Schemas (PatchBot)


class FailureFixCreate(BaseModel):
    """Schema for creating a failure fix record."""

    failure_signature: str = Field(..., max_length=255)
    repository: str = Field(..., max_length=255)
    branch: Optional[str] = Field(None, max_length=100)
    failure_type: str = Field(..., max_length=50)
    build_url: Optional[str] = Field(None, max_length=500)
    error_message: Optional[str] = Field(None, max_length=1000)


class FailureFixUpdate(BaseModel):
    """Schema for updating a failure fix."""

    fix_pr_url: Optional[str] = None
    fix_pr_number: Optional[int] = None
    fix_confidence: Optional[float] = Field(None, ge=0.0, le=1.0)
    fix_diff: Optional[str] = None
    fix_success: Optional[bool] = None
    fix_merged: Optional[bool] = None
    time_to_fix_seconds: Optional[int] = None
    time_to_merge_seconds: Optional[int] = None


class FailureFixResponse(BaseModel):
    """Schema for failure fix response."""

    id: UUID
    agent_task_id: UUID
    failure_signature: str
    repository: str
    branch: Optional[str]
    failure_type: str
    fix_pr_url: Optional[str]
    fix_pr_number: Optional[int]
    fix_confidence: Optional[float]
    fix_success: Optional[bool]
    fix_merged: bool
    time_to_fix_seconds: Optional[int]
    time_to_merge_seconds: Optional[int]
    build_url: Optional[str]
    error_message: Optional[str]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# Statistics


class AgentStatistics(BaseModel):
    """Agent performance statistics."""

    total_agents: int
    active_agents: int
    paused_agents: int
    failed_agents: int


class TaskStatistics(BaseModel):
    """Task execution statistics."""

    total_tasks: int
    pending_tasks: int
    running_tasks: int
    completed_tasks: int
    failed_tasks: int
    rate_limited_tasks: int
    avg_duration_ms: Optional[float]
    success_rate: float


class FixStatistics(BaseModel):
    """Failure fix statistics."""

    total_fixes: int
    successful_fixes: int
    merged_fixes: int
    avg_time_to_fix_seconds: Optional[float]
    avg_time_to_merge_seconds: Optional[float]
    success_rate: float
    fixes_by_type: Dict[str, int]


# Pagination


class PaginatedResponse(BaseModel):
    """Generic paginated response."""

    items: List[Any]
    total: int
    page: int
    page_size: int
    pages: int

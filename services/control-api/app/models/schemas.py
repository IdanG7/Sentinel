"""Pydantic schemas for API requests and responses."""

from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


# Auth Schemas
class LoginRequest(BaseModel):
    """Login request schema."""

    username: str = Field(..., min_length=3, max_length=50)
    password: str = Field(..., min_length=8)


class TokenResponse(BaseModel):
    """Token response schema."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshTokenRequest(BaseModel):
    """Refresh token request schema."""

    refresh_token: str


# Workload Schemas
class WorkloadType(str, Enum):
    """Workload type enumeration."""

    TRAINING = "training"
    INFERENCE = "inference"
    BATCH = "batch"


class WorkloadResources(BaseModel):
    """Workload resource requirements."""

    cpu: str = Field(..., description="CPU request (e.g., '4' or '4000m')")
    memory: str = Field(..., description="Memory request (e.g., '8Gi')")
    gpu: dict[str, Any] | None = Field(
        None, description="GPU requirements: {count: 1, sku: 'L4'}"
    )


class WorkloadCreate(BaseModel):
    """Create workload request."""

    name: str = Field(..., min_length=3, max_length=255)
    type: WorkloadType
    image: str = Field(..., min_length=5, max_length=512)
    resources: WorkloadResources
    env: dict[str, str] | None = None
    config_ref: str | None = None


class WorkloadResponse(BaseModel):
    """Workload response schema."""

    id: UUID
    name: str
    type: WorkloadType
    image: str
    resources: dict[str, Any]
    env: dict[str, str] | None = None
    config_ref: str | None = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# Deployment Schemas
class DeploymentStrategy(str, Enum):
    """Deployment strategy enumeration."""

    ROLLING = "rolling"
    CANARY = "canary"
    BLUE_GREEN = "blue_green"


class CanaryConfig(BaseModel):
    """Canary deployment configuration."""

    steps: list[dict[str, int]] = Field(
        ..., description="Canary steps: [{percent: 10}, {percent: 50}, {percent: 100}]"
    )


class DeploymentCreate(BaseModel):
    """Create deployment request."""

    workload_id: UUID
    cluster_id: UUID
    strategy: DeploymentStrategy = DeploymentStrategy.ROLLING
    replicas: int = Field(1, ge=0, le=100)
    canary_config: CanaryConfig | None = None


class DeploymentStatus(str, Enum):
    """Deployment status enumeration."""

    PENDING = "pending"
    DEPLOYING = "deploying"
    RUNNING = "running"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"


class DeploymentResponse(BaseModel):
    """Deployment response schema."""

    id: UUID
    workload_id: UUID
    cluster_id: UUID
    strategy: DeploymentStrategy
    replicas: int
    canary_config: dict[str, Any] | None = None
    status: DeploymentStatus
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ScaleRequest(BaseModel):
    """Scale deployment request."""

    replicas: int = Field(..., ge=0, le=100)


# Policy Schemas
class PolicyRuleType(str, Enum):
    """Policy rule type enumeration."""

    COST_CEILING = "cost_ceiling"
    RATE_LIMIT = "rate_limit"
    SLA = "sla"
    SLO = "slo"
    QUOTA = "quota"


class PolicyRule(BaseModel):
    """Policy rule schema."""

    type: PolicyRuleType
    selector: dict[str, str] | None = None
    constraint: dict[str, Any]
    action_on_violation: str = "reject"


class PolicyCreate(BaseModel):
    """Create policy request."""

    name: str = Field(..., min_length=3, max_length=255)
    rules: list[PolicyRule]
    priority: int = Field(0, ge=0, le=1000)
    enabled: bool = True


class PolicyResponse(BaseModel):
    """Policy response schema."""

    id: UUID
    name: str
    rules: list[dict[str, Any]]
    priority: int
    enabled: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# Action Plan Schemas
class DecisionVerb(str, Enum):
    """Decision verb enumeration."""

    SCALE = "scale"
    RESCHEDULE = "reschedule"
    ROLLBACK = "rollback"
    RESTART = "restart"
    DRAIN = "drain"


class Decision(BaseModel):
    """Decision schema."""

    verb: DecisionVerb
    target: dict[str, str] = Field(..., description="Target resource identifiers")
    params: dict[str, Any] = Field(..., description="Action parameters")
    ttl: int = Field(900, ge=60, le=3600, description="Time-to-live in seconds")
    safety: dict[str, Any] | None = None


class ActionPlanSource(str, Enum):
    """Action plan source enumeration."""

    USER = "user"
    POLICY = "policy"
    INFRAMIND = "InfraMind"


class ActionPlanCreate(BaseModel):
    """Create action plan request."""

    decisions: list[Decision]
    source: ActionPlanSource
    correlation_id: str | None = None


class ActionPlanStatus(str, Enum):
    """Action plan status enumeration."""

    PENDING = "pending"
    VALIDATING = "validating"
    APPROVED = "approved"
    EXECUTING = "executing"
    COMPLETED = "completed"
    FAILED = "failed"
    REJECTED = "rejected"


class ActionPlanResponse(BaseModel):
    """Action plan response schema."""

    id: UUID
    decisions: list[dict[str, Any]]
    source: ActionPlanSource
    correlation_id: str | None = None
    status: ActionPlanStatus
    created_at: datetime
    executed_at: datetime | None = None

    class Config:
        from_attributes = True


# Audit Log Schemas
class AuditLogResponse(BaseModel):
    """Audit log response schema."""

    id: UUID
    timestamp: datetime
    actor: str
    verb: str
    target: dict[str, Any]
    result: str
    reason: str | None = None
    metadata: dict[str, Any] | None = None

    class Config:
        from_attributes = True


# Health & Status
class HealthResponse(BaseModel):
    """Health check response."""

    status: str
    version: str
    timestamp: datetime


class MetricsResponse(BaseModel):
    """Metrics summary response."""

    deployments_total: int
    policies_total: int
    action_plans_last_hour: int
    policy_violations_last_hour: int

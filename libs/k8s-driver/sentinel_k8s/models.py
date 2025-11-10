"""Kubernetes resource models for Sentinel."""

from datetime import datetime
from enum import Enum
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class ResourceStatus(str, Enum):
    """Kubernetes resource status."""

    PENDING = "pending"
    CREATING = "creating"
    RUNNING = "running"
    SCALING = "scaling"
    UPDATING = "updating"
    DELETING = "deleting"
    FAILED = "failed"
    UNKNOWN = "unknown"


class ClusterConfig(BaseModel):
    """Cluster configuration."""

    id: UUID
    name: str
    kubeconfig_path: Optional[str] = None
    kubeconfig_data: Optional[str] = None  # Base64 encoded kubeconfig
    context: Optional[str] = None  # Specific context to use
    namespace: str = "default"
    labels: dict[str, str] = Field(default_factory=dict)
    gpu_families: list[str] = Field(default_factory=list)


class ResourceSpec(BaseModel):
    """Kubernetes resource specification."""

    name: str
    namespace: str = "default"
    labels: dict[str, str] = Field(default_factory=dict)
    annotations: dict[str, str] = Field(default_factory=dict)


class DeploymentSpec(ResourceSpec):
    """Deployment specification."""

    replicas: int = 1
    image: str
    command: Optional[list[str]] = None
    args: Optional[list[str]] = None
    env: dict[str, str] = Field(default_factory=dict)
    resources: dict[str, Any] = Field(default_factory=dict)
    ports: list[dict[str, Any]] = Field(default_factory=list)
    volumes: list[dict[str, Any]] = Field(default_factory=list)
    volume_mounts: list[dict[str, Any]] = Field(default_factory=list)


class JobSpec(ResourceSpec):
    """Job specification."""

    image: str
    command: Optional[list[str]] = None
    args: Optional[list[str]] = None
    env: dict[str, str] = Field(default_factory=dict)
    resources: dict[str, Any] = Field(default_factory=dict)
    backoff_limit: int = 3
    ttl_seconds_after_finished: Optional[int] = None
    parallelism: int = 1
    completions: int = 1


class StatefulSetSpec(ResourceSpec):
    """StatefulSet specification."""

    replicas: int = 1
    service_name: str
    image: str
    command: Optional[list[str]] = None
    args: Optional[list[str]] = None
    env: dict[str, str] = Field(default_factory=dict)
    resources: dict[str, Any] = Field(default_factory=dict)
    ports: list[dict[str, Any]] = Field(default_factory=list)
    volume_claim_templates: list[dict[str, Any]] = Field(default_factory=list)


class ResourceStatus(BaseModel):
    """Kubernetes resource status."""

    name: str
    namespace: str
    kind: str
    status: str
    replicas: Optional[int] = None
    ready_replicas: Optional[int] = None
    available_replicas: Optional[int] = None
    conditions: list[dict[str, Any]] = Field(default_factory=list)
    created_at: Optional[datetime] = None
    message: Optional[str] = None


class ScaleOperation(BaseModel):
    """Scale operation request."""

    name: str
    namespace: str
    replicas: int
    timeout_seconds: int = 300


class WatchEvent(BaseModel):
    """Kubernetes watch event."""

    event_type: str  # ADDED, MODIFIED, DELETED, ERROR
    resource_type: str
    name: str
    namespace: str
    object: dict[str, Any]
    timestamp: datetime = Field(default_factory=datetime.utcnow)

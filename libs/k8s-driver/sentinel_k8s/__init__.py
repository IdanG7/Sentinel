"""Sentinel Kubernetes Driver - Multi-cluster K8s resource management."""

from .canary import CanaryConfig, CanaryDeployment, CanaryDeploymentController, CanaryPhase
from .cluster import ClusterConnection, ClusterManager
from .deployments import DeploymentManager
from .health import DeploymentHealthChecker, HealthCheckResult, HealthStatus
from .jobs import JobManager
from .models import (
    ClusterConfig,
    DeploymentSpec,
    JobSpec,
    ResourceSpec,
    ResourceStatus,
    ScaleOperation,
    StatefulSetSpec,
    WatchEvent,
)
from .statefulsets import StatefulSetManager
from .watch import ReconciliationLoop, ResourceWatcher

__version__ = "0.1.0"

__all__ = [
    # Cluster management
    "ClusterManager",
    "ClusterConnection",
    # Resource managers
    "DeploymentManager",
    "JobManager",
    "StatefulSetManager",
    # Health checking
    "DeploymentHealthChecker",
    "HealthCheckResult",
    "HealthStatus",
    # Canary deployments
    "CanaryDeploymentController",
    "CanaryDeployment",
    "CanaryConfig",
    "CanaryPhase",
    # Watch and reconciliation
    "ResourceWatcher",
    "ReconciliationLoop",
    # Models
    "ClusterConfig",
    "ResourceSpec",
    "DeploymentSpec",
    "JobSpec",
    "StatefulSetSpec",
    "ResourceStatus",
    "ScaleOperation",
    "WatchEvent",
]

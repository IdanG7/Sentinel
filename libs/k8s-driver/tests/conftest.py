"""Pytest configuration and fixtures for K8s driver tests."""

import pytest
from unittest.mock import MagicMock, Mock
from kubernetes import client


@pytest.fixture
def mock_cluster_connection():
    """Mock cluster connection for testing."""
    mock_conn = MagicMock()
    mock_conn.core_v1 = MagicMock(spec=client.CoreV1Api)
    mock_conn.apps_v1 = MagicMock(spec=client.AppsV1Api)
    mock_conn.batch_v1 = MagicMock(spec=client.BatchV1Api)
    return mock_conn


@pytest.fixture
def sample_deployment_spec():
    """Sample deployment specification for testing."""
    from sentinel_k8s import DeploymentSpec

    return DeploymentSpec(
        name="test-deployment",
        namespace="default",
        replicas=3,
        image="nginx:latest",
        labels={"app": "test"},
        resources={
            "requests": {"cpu": "100m", "memory": "128Mi"},
            "limits": {"cpu": "200m", "memory": "256Mi"},
        },
    )


@pytest.fixture
def sample_job_spec():
    """Sample job specification for testing."""
    from sentinel_k8s import JobSpec

    return JobSpec(
        name="test-job",
        namespace="default",
        image="busybox:latest",
        command=["sh", "-c", "echo hello world"],
        backoff_limit=3,
        parallelism=1,
        completions=1,
    )


@pytest.fixture
def mock_k8s_deployment():
    """Mock Kubernetes Deployment object."""
    deployment = Mock(spec=client.V1Deployment)
    deployment.metadata = Mock()
    deployment.metadata.name = "test-deployment"
    deployment.metadata.namespace = "default"
    deployment.metadata.labels = {"app": "sentinel", "workload": "test"}
    deployment.metadata.creation_timestamp = "2024-01-01T00:00:00Z"

    deployment.spec = Mock()
    deployment.spec.replicas = 3

    deployment.status = Mock()
    deployment.status.replicas = 3
    deployment.status.ready_replicas = 3
    deployment.status.available_replicas = 3
    deployment.status.conditions = [
        Mock(type="Available", status="True", reason="MinimumReplicasAvailable", message="Deployment has minimum availability"),
        Mock(type="Progressing", status="True", reason="NewReplicaSetAvailable", message="ReplicaSet has successfully progressed"),
    ]

    return deployment

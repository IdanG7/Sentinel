"""Tests for DeploymentManager."""

import pytest
from unittest.mock import Mock, patch
from kubernetes.client.exceptions import ApiException

from sentinel_k8s import DeploymentManager, DeploymentSpec


class TestDeploymentManager:
    """Test cases for DeploymentManager."""

    def test_init(self, mock_cluster_connection):
        """Test DeploymentManager initialization."""
        manager = DeploymentManager(mock_cluster_connection)
        assert manager.cluster == mock_cluster_connection
        assert manager.apps_v1 == mock_cluster_connection.apps_v1

    def test_create_deployment(self, mock_cluster_connection, sample_deployment_spec, mock_k8s_deployment):
        """Test creating a deployment."""
        mock_cluster_connection.apps_v1.create_namespaced_deployment.return_value = mock_k8s_deployment

        manager = DeploymentManager(mock_cluster_connection)
        result = manager.create(sample_deployment_spec)

        # Verify create was called
        mock_cluster_connection.apps_v1.create_namespaced_deployment.assert_called_once()

        # Verify namespace
        call_args = mock_cluster_connection.apps_v1.create_namespaced_deployment.call_args
        assert call_args.kwargs["namespace"] == "default"

        # Verify deployment was created
        assert result == mock_k8s_deployment

    def test_get_deployment_exists(self, mock_cluster_connection, mock_k8s_deployment):
        """Test getting an existing deployment."""
        mock_cluster_connection.apps_v1.read_namespaced_deployment.return_value = mock_k8s_deployment

        manager = DeploymentManager(mock_cluster_connection)
        result = manager.get("test-deployment", "default")

        mock_cluster_connection.apps_v1.read_namespaced_deployment.assert_called_once_with("test-deployment", "default")
        assert result == mock_k8s_deployment

    def test_get_deployment_not_found(self, mock_cluster_connection):
        """Test getting a non-existent deployment."""
        mock_cluster_connection.apps_v1.read_namespaced_deployment.side_effect = ApiException(status=404)

        manager = DeploymentManager(mock_cluster_connection)
        result = manager.get("nonexistent", "default")

        assert result is None

    def test_scale_deployment(self, mock_cluster_connection, mock_k8s_deployment):
        """Test scaling a deployment."""
        mock_cluster_connection.apps_v1.patch_namespaced_deployment_scale.return_value = mock_k8s_deployment

        manager = DeploymentManager(mock_cluster_connection)
        result = manager.scale("test-deployment", "default", 5)

        mock_cluster_connection.apps_v1.patch_namespaced_deployment_scale.assert_called_once()
        call_args = mock_cluster_connection.apps_v1.patch_namespaced_deployment_scale.call_args
        assert call_args.args[0] == "test-deployment"
        assert call_args.args[1] == "default"
        assert call_args.kwargs["body"]["spec"]["replicas"] == 5

    def test_delete_deployment_success(self, mock_cluster_connection):
        """Test deleting a deployment successfully."""
        manager = DeploymentManager(mock_cluster_connection)
        result = manager.delete("test-deployment", "default")

        mock_cluster_connection.apps_v1.delete_namespaced_deployment.assert_called_once_with("test-deployment", "default")
        assert result is True

    def test_delete_deployment_not_found(self, mock_cluster_connection):
        """Test deleting a non-existent deployment."""
        mock_cluster_connection.apps_v1.delete_namespaced_deployment.side_effect = ApiException(status=404)

        manager = DeploymentManager(mock_cluster_connection)
        result = manager.delete("nonexistent", "default")

        assert result is False

    def test_get_status(self, mock_cluster_connection, mock_k8s_deployment):
        """Test getting deployment status."""
        mock_cluster_connection.apps_v1.read_namespaced_deployment.return_value = mock_k8s_deployment

        manager = DeploymentManager(mock_cluster_connection)
        status = manager.get_status("test-deployment", "default")

        assert status is not None
        assert status.name == "test-deployment"
        assert status.namespace == "default"
        assert status.kind == "Deployment"
        assert status.status == "running"
        assert status.replicas == 3
        assert status.ready_replicas == 3
        assert status.available_replicas == 3
        assert len(status.conditions) == 2

    def test_get_status_scaling(self, mock_cluster_connection, mock_k8s_deployment):
        """Test deployment status when scaling."""
        # Modify mock to simulate scaling state
        mock_k8s_deployment.status.ready_replicas = 2
        mock_k8s_deployment.spec.replicas = 3

        mock_cluster_connection.apps_v1.read_namespaced_deployment.return_value = mock_k8s_deployment

        manager = DeploymentManager(mock_cluster_connection)
        status = manager.get_status("test-deployment", "default")

        assert status.status == "scaling"

    def test_list_deployments(self, mock_cluster_connection, mock_k8s_deployment):
        """Test listing deployments."""
        mock_list = Mock()
        mock_list.items = [mock_k8s_deployment]
        mock_cluster_connection.apps_v1.list_namespaced_deployment.return_value = mock_list

        manager = DeploymentManager(mock_cluster_connection)
        result = manager.list("default", labels={"app": "sentinel"})

        mock_cluster_connection.apps_v1.list_namespaced_deployment.assert_called_once()
        call_args = mock_cluster_connection.apps_v1.list_namespaced_deployment.call_args
        assert call_args.kwargs["namespace"] == "default"
        assert call_args.kwargs["label_selector"] == "app=sentinel"
        assert len(result) == 1
        assert result[0] == mock_k8s_deployment

    def test_create_with_labels(self, mock_cluster_connection, sample_deployment_spec, mock_k8s_deployment):
        """Test that Sentinel labels are added to deployments."""
        mock_cluster_connection.apps_v1.create_namespaced_deployment.return_value = mock_k8s_deployment

        manager = DeploymentManager(mock_cluster_connection)
        manager.create(sample_deployment_spec)

        call_args = mock_cluster_connection.apps_v1.create_namespaced_deployment.call_args
        deployment_body = call_args.kwargs["body"]

        # Verify Sentinel labels are added
        assert deployment_body.metadata.labels["app"] == "sentinel"
        assert deployment_body.metadata.labels["managed-by"] == "sentinel"
        assert deployment_body.metadata.labels["workload"] == "test-deployment"
        # Verify original labels are preserved
        assert deployment_body.metadata.labels["app"] == "sentinel"

    def test_create_with_resources(self, mock_cluster_connection, sample_deployment_spec, mock_k8s_deployment):
        """Test creating deployment with resource limits."""
        mock_cluster_connection.apps_v1.create_namespaced_deployment.return_value = mock_k8s_deployment

        manager = DeploymentManager(mock_cluster_connection)
        manager.create(sample_deployment_spec)

        call_args = mock_cluster_connection.apps_v1.create_namespaced_deployment.call_args
        deployment_body = call_args.kwargs["body"]
        container = deployment_body.spec.template.spec.containers[0]

        assert container.resources is not None

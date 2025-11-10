"""Multi-cluster Kubernetes client management."""

import base64
import tempfile
from pathlib import Path
from typing import Optional
from uuid import UUID

from kubernetes import client, config
from kubernetes.client import ApiClient, AppsV1Api, BatchV1Api, CoreV1Api
from kubernetes.client.exceptions import ApiException

from .models import ClusterConfig


class ClusterManager:
    """Manages multiple Kubernetes cluster connections."""

    def __init__(self):
        """Initialize cluster manager."""
        self._clusters: dict[UUID, ClusterConnection] = {}

    def add_cluster(self, cluster_config: ClusterConfig) -> "ClusterConnection":
        """
        Add a cluster to the manager.

        Args:
            cluster_config: Cluster configuration

        Returns:
            ClusterConnection instance

        Raises:
            ValueError: If cluster configuration is invalid
        """
        if cluster_config.id in self._clusters:
            return self._clusters[cluster_config.id]

        connection = ClusterConnection(cluster_config)
        self._clusters[cluster_config.id] = connection
        return connection

    def get_cluster(self, cluster_id: UUID) -> Optional["ClusterConnection"]:
        """
        Get a cluster connection by ID.

        Args:
            cluster_id: Cluster UUID

        Returns:
            ClusterConnection or None if not found
        """
        return self._clusters.get(cluster_id)

    def remove_cluster(self, cluster_id: UUID) -> bool:
        """
        Remove a cluster from the manager.

        Args:
            cluster_id: Cluster UUID

        Returns:
            True if removed, False if not found
        """
        if cluster_id in self._clusters:
            connection = self._clusters[cluster_id]
            connection.close()
            del self._clusters[cluster_id]
            return True
        return False

    def list_clusters(self) -> list[ClusterConfig]:
        """
        List all registered clusters.

        Returns:
            List of cluster configurations
        """
        return [conn.config for conn in self._clusters.values()]

    def close_all(self):
        """Close all cluster connections."""
        for connection in self._clusters.values():
            connection.close()
        self._clusters.clear()


class ClusterConnection:
    """Represents a connection to a single Kubernetes cluster."""

    def __init__(self, cluster_config: ClusterConfig):
        """
        Initialize cluster connection.

        Args:
            cluster_config: Cluster configuration

        Raises:
            ValueError: If kubeconfig is invalid
        """
        self.config = cluster_config
        self._api_client: Optional[ApiClient] = None
        self._core_v1: Optional[CoreV1Api] = None
        self._apps_v1: Optional[AppsV1Api] = None
        self._batch_v1: Optional[BatchV1Api] = None
        self._temp_kubeconfig: Optional[Path] = None

        self._initialize_client()

    def _initialize_client(self):
        """Initialize Kubernetes API client."""
        try:
            if self.config.kubeconfig_data:
                # Decode base64 kubeconfig and write to temp file
                kubeconfig_content = base64.b64decode(self.config.kubeconfig_data)
                with tempfile.NamedTemporaryFile(mode="wb", delete=False) as f:
                    f.write(kubeconfig_content)
                    self._temp_kubeconfig = Path(f.name)
                config.load_kube_config(
                    config_file=str(self._temp_kubeconfig),
                    context=self.config.context,
                )
            elif self.config.kubeconfig_path:
                # Load from file path
                config.load_kube_config(
                    config_file=self.config.kubeconfig_path,
                    context=self.config.context,
                )
            else:
                # Try in-cluster config (for when running inside K8s)
                config.load_incluster_config()

            # Create API client
            self._api_client = ApiClient()
            self._core_v1 = CoreV1Api(self._api_client)
            self._apps_v1 = AppsV1Api(self._api_client)
            self._batch_v1 = BatchV1Api(self._api_client)

        except Exception as e:
            raise ValueError(f"Failed to initialize cluster connection: {e}") from e

    @property
    def core_v1(self) -> CoreV1Api:
        """Get CoreV1Api instance."""
        if not self._core_v1:
            raise RuntimeError("Cluster connection not initialized")
        return self._core_v1

    @property
    def apps_v1(self) -> AppsV1Api:
        """Get AppsV1Api instance."""
        if not self._apps_v1:
            raise RuntimeError("Cluster connection not initialized")
        return self._apps_v1

    @property
    def batch_v1(self) -> BatchV1Api:
        """Get BatchV1Api instance."""
        if not self._batch_v1:
            raise RuntimeError("Cluster connection not initialized")
        return self._batch_v1

    @property
    def api_client(self) -> ApiClient:
        """Get ApiClient instance."""
        if not self._api_client:
            raise RuntimeError("Cluster connection not initialized")
        return self._api_client

    def is_healthy(self) -> bool:
        """
        Check if cluster connection is healthy.

        Returns:
            True if cluster is reachable and healthy
        """
        try:
            self.core_v1.get_api_resources()
            return True
        except ApiException:
            return False

    def get_cluster_version(self) -> dict:
        """
        Get Kubernetes cluster version information.

        Returns:
            Version info dict

        Raises:
            ApiException: If unable to get version
        """
        version_api = client.VersionApi(self.api_client)
        version_info = version_api.get_code()
        return {
            "major": version_info.major,
            "minor": version_info.minor,
            "git_version": version_info.git_version,
            "platform": version_info.platform,
        }

    def close(self):
        """Close the cluster connection and clean up resources."""
        if self._api_client:
            self._api_client.close()
            self._api_client = None

        # Clean up temporary kubeconfig file
        if self._temp_kubeconfig and self._temp_kubeconfig.exists():
            self._temp_kubeconfig.unlink()
            self._temp_kubeconfig = None

        self._core_v1 = None
        self._apps_v1 = None
        self._batch_v1 = None

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()

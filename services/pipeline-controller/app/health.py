"""Health checking for deployments."""

import logging
from typing import Any
from uuid import UUID

from sentinel_k8s import ClusterManager, DeploymentManager  # type: ignore[import-not-found]

from .config import Settings

logger = logging.getLogger(__name__)


class HealthChecker:
    """
    Monitors health of deployments and triggers rollbacks if needed.
    """

    def __init__(self, cluster_manager: ClusterManager, settings: Settings):
        """
        Initialize health checker.

        Args:
            cluster_manager: Cluster manager instance
            settings: Application settings
        """
        self.cluster_manager = cluster_manager
        self.settings = settings
        self._health_history: dict[UUID, list[bool]] = {}

    async def check_deployment_health(
        self, deployment_id: UUID, deployment_data: dict[str, Any]
    ) -> bool:
        """
        Check health of a deployment.

        Args:
            deployment_id: Deployment UUID
            deployment_data: Deployment metadata

        Returns:
            True if healthy, False otherwise
        """
        try:
            # Get cluster connection
            cluster = self.cluster_manager.get_cluster("default")
            if not cluster:
                logger.error("Default cluster not configured")
                return False

            # Create deployment manager
            deployment_manager = DeploymentManager(cluster)

            # Get deployment status
            deployment_name = f"deployment-{deployment_id}"
            status = deployment_manager.get_status(
                name=deployment_name,
                namespace=self.settings.default_namespace,
            )

            if not status:
                logger.warning(f"Deployment {deployment_id} not found")
                return False

            # Check if deployment is healthy
            is_healthy = self._evaluate_health(status, deployment_data)

            # Track health history
            if deployment_id not in self._health_history:
                self._health_history[deployment_id] = []

            self._health_history[deployment_id].append(is_healthy)

            # Keep only last 10 health checks
            if len(self._health_history[deployment_id]) > 10:
                self._health_history[deployment_id].pop(0)

            # Check failure threshold
            if not is_healthy:
                recent_checks = self._health_history[deployment_id][-5:]
                failure_rate = (
                    len([x for x in recent_checks if not x]) / len(recent_checks)
                ) * 100

                if failure_rate >= self.settings.rollback_threshold_failure_percent:
                    logger.error(
                        f"Deployment {deployment_id} failure rate {failure_rate:.1f}% "
                        f"exceeds threshold {self.settings.rollback_threshold_failure_percent}%"
                    )
                    return False

            return is_healthy

        except Exception as e:
            logger.error(
                f"Error checking health for {deployment_id}: {e}", exc_info=True
            )
            return False

    def _evaluate_health(self, status: Any, deployment_data: dict[str, Any]) -> bool:
        """
        Evaluate if deployment status indicates health.

        Args:
            status: Deployment status from K8s
            deployment_data: Deployment metadata

        Returns:
            True if healthy
        """
        # Check if desired replicas match ready replicas
        desired_replicas = deployment_data.get("replicas", 1)
        ready_replicas = status.ready_replicas or 0

        if ready_replicas < desired_replicas:
            logger.warning(
                f"Deployment unhealthy: {ready_replicas}/{desired_replicas} replicas ready"
            )
            return False

        # Check deployment conditions
        for condition in status.conditions:
            condition_type = condition.get("type")
            condition_status = condition.get("status")

            # Check for progressing condition
            if condition_type == "Progressing" and condition_status != "True":
                logger.warning(
                    f"Deployment not progressing: {condition.get('message')}"
                )
                return False

            # Check for available condition
            if condition_type == "Available" and condition_status != "True":
                logger.warning(f"Deployment not available: {condition.get('message')}")
                return False

        return True

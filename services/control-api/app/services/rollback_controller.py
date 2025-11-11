"""Rollback Controller - Monitors deployments and triggers automatic rollbacks."""

import asyncio
import logging
from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from sentinel_k8s import DeploymentHealthChecker, HealthStatus

logger = logging.getLogger(__name__)


class RollbackReason(str, Enum):
    """Reason for triggering a rollback."""

    HEALTH_CHECK_FAILED = "health_check_failed"
    ERROR_RATE_HIGH = "error_rate_high"
    MANUAL = "manual"
    POLICY_VIOLATION = "policy_violation"


class RollbackStatus(str, Enum):
    """Rollback execution status."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


class RollbackController:
    """
    Rollback controller for automated deployment rollbacks.

    Monitors deployment health and automatically rolls back
    deployments that fail health checks or violate SLOs.
    """

    def __init__(
        self,
        k8s_driver: Any | None = None,
        health_check_interval: int = 30,
        health_check_window: int = 300,
        min_health_score: float = 0.6,
    ):
        """
        Initialize rollback controller.

        Args:
            k8s_driver: Kubernetes driver for deployment operations
            health_check_interval: Seconds between health checks
            health_check_window: Seconds to monitor after deployment
            min_health_score: Minimum health score to avoid rollback (0.0-1.0)
        """
        self.k8s_driver = k8s_driver
        self.health_check_interval = health_check_interval
        self.health_check_window = health_check_window
        self.min_health_score = min_health_score

        # Tracking state
        self._monitored_deployments: dict[str, dict[str, Any]] = {}
        self._rollback_history: dict[UUID, dict[str, Any]] = {}
        self._monitoring_tasks: dict[str, asyncio.Task] = {}

    async def monitor_deployment(
        self,
        deployment_id: str,
        name: str,
        namespace: str = "default",
        cluster_id: str = "default",
        revision: str | None = None,
        auto_rollback: bool = True,
    ) -> UUID:
        """
        Start monitoring a deployment for health issues.

        Args:
            deployment_id: Unique deployment identifier
            name: Deployment name
            namespace: Kubernetes namespace
            cluster_id: Cluster identifier
            revision: Previous revision to rollback to (optional)
            auto_rollback: Automatically trigger rollback on failure

        Returns:
            Monitoring session ID
        """
        session_id = uuid4()

        monitoring_config = {
            "session_id": session_id,
            "deployment_id": deployment_id,
            "name": name,
            "namespace": namespace,
            "cluster_id": cluster_id,
            "revision": revision,
            "auto_rollback": auto_rollback,
            "started_at": datetime.utcnow(),
            "last_check": None,
            "check_count": 0,
            "health_scores": [],
        }

        self._monitored_deployments[deployment_id] = monitoring_config

        # Start monitoring task
        task = asyncio.create_task(self._monitoring_loop(deployment_id, monitoring_config))
        self._monitoring_tasks[deployment_id] = task

        logger.info(
            f"Started monitoring deployment {name} "
            f"(session: {session_id}, auto_rollback: {auto_rollback})"
        )

        return session_id

    async def _monitoring_loop(self, deployment_id: str, config: dict[str, Any]) -> None:
        """
        Continuous monitoring loop for a deployment.

        Args:
            deployment_id: Deployment to monitor
            config: Monitoring configuration
        """
        name = config["name"]
        namespace = config["namespace"]
        auto_rollback = config["auto_rollback"]
        started_at = config["started_at"]

        try:
            while True:
                # Check if monitoring window expired
                elapsed = (datetime.utcnow() - started_at).total_seconds()
                if elapsed > self.health_check_window:
                    logger.info(f"Monitoring window expired for {name} after {elapsed:.0f}s")
                    break

                # Perform health check
                health_result = await self._check_deployment_health(name, namespace)

                # Update monitoring state
                config["last_check"] = datetime.utcnow()
                config["check_count"] += 1
                config["health_scores"].append(health_result.score)

                logger.info(
                    f"Health check for {name}: {health_result.status.value} "
                    f"(score: {health_result.score:.2f})"
                )

                # Check if rollback is needed
                if health_result.score < self.min_health_score:
                    logger.warning(
                        f"Deployment {name} health score {health_result.score:.2f} "
                        f"below threshold {self.min_health_score}"
                    )

                    if auto_rollback:
                        await self.trigger_rollback(
                            deployment_id=deployment_id,
                            reason=RollbackReason.HEALTH_CHECK_FAILED,
                            metadata={
                                "health_score": health_result.score,
                                "health_status": health_result.status.value,
                                "health_message": health_result.message,
                                "checks_failed": config["check_count"],
                            },
                        )
                        break  # Stop monitoring after triggering rollback

                # Wait for next check
                await asyncio.sleep(self.health_check_interval)

        except asyncio.CancelledError:
            logger.info(f"Monitoring cancelled for {name}")
            raise
        except Exception as e:
            logger.error(f"Error in monitoring loop for {name}: {e}", exc_info=True)
        finally:
            # Cleanup
            if deployment_id in self._monitored_deployments:
                del self._monitored_deployments[deployment_id]
            if deployment_id in self._monitoring_tasks:
                del self._monitoring_tasks[deployment_id]

    async def _check_deployment_health(self, name: str, namespace: str) -> Any:
        """
        Check deployment health.

        Args:
            name: Deployment name
            namespace: Namespace

        Returns:
            HealthCheckResult
        """
        if self.k8s_driver:
            # Use real health checker
            # Note: In a full implementation, get cluster connection from driver
            # For now, return a mock result
            pass

        # Mock health check for development
        from sentinel_k8s import HealthCheckResult

        return HealthCheckResult(
            status=HealthStatus.HEALTHY,
            message="Deployment is healthy (mocked)",
            checked_at=datetime.utcnow(),
            details={},
            score=0.95,
        )

    async def trigger_rollback(
        self,
        deployment_id: str,
        reason: RollbackReason,
        metadata: dict[str, Any] | None = None,
    ) -> UUID:
        """
        Trigger a deployment rollback.

        Args:
            deployment_id: Deployment to rollback
            reason: Reason for rollback
            metadata: Additional metadata

        Returns:
            Rollback operation ID
        """
        rollback_id = uuid4()

        config = self._monitored_deployments.get(deployment_id)
        if not config:
            raise ValueError(f"Deployment {deployment_id} not being monitored")

        name = config["name"]
        namespace = config["namespace"]
        revision = config.get("revision", "previous")

        rollback_record = {
            "rollback_id": rollback_id,
            "deployment_id": deployment_id,
            "name": name,
            "namespace": namespace,
            "revision": revision,
            "reason": reason.value,
            "triggered_at": datetime.utcnow(),
            "completed_at": None,
            "status": RollbackStatus.PENDING.value,
            "metadata": metadata or {},
        }

        self._rollback_history[rollback_id] = rollback_record

        logger.info(
            f"Triggering rollback for {name} to revision {revision} "
            f"(reason: {reason.value}, rollback_id: {rollback_id})"
        )

        # Execute rollback
        rollback_record["status"] = RollbackStatus.IN_PROGRESS.value

        try:
            if self.k8s_driver:
                # Execute actual rollback using K8s driver
                # await self.k8s_driver.rollback_deployment(...)
                pass

            # Mock rollback execution
            await asyncio.sleep(1.0)

            rollback_record["status"] = RollbackStatus.COMPLETED.value
            rollback_record["completed_at"] = datetime.utcnow()

            logger.info(f"Rollback {rollback_id} completed successfully")

        except Exception as e:
            rollback_record["status"] = RollbackStatus.FAILED.value
            rollback_record["error"] = str(e)
            rollback_record["completed_at"] = datetime.utcnow()

            logger.error(f"Rollback {rollback_id} failed: {e}", exc_info=True)
            raise

        return rollback_id

    def get_rollback_status(self, rollback_id: UUID) -> dict[str, Any] | None:
        """
        Get status of a rollback operation.

        Args:
            rollback_id: Rollback operation ID

        Returns:
            Rollback status dict or None if not found
        """
        return self._rollback_history.get(rollback_id)

    def get_monitoring_status(self, deployment_id: str) -> dict[str, Any] | None:
        """
        Get monitoring status for a deployment.

        Args:
            deployment_id: Deployment identifier

        Returns:
            Monitoring status dict or None if not being monitored
        """
        config = self._monitored_deployments.get(deployment_id)
        if not config:
            return None

        return {
            "deployment_id": deployment_id,
            "name": config["name"],
            "namespace": config["namespace"],
            "started_at": config["started_at"],
            "last_check": config["last_check"],
            "check_count": config["check_count"],
            "average_health_score": (
                sum(config["health_scores"]) / len(config["health_scores"])
                if config["health_scores"]
                else 0.0
            ),
            "auto_rollback": config["auto_rollback"],
        }

    async def stop_monitoring(self, deployment_id: str) -> bool:
        """
        Stop monitoring a deployment.

        Args:
            deployment_id: Deployment to stop monitoring

        Returns:
            True if monitoring was stopped, False if not being monitored
        """
        task = self._monitoring_tasks.get(deployment_id)
        if task:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

            logger.info(f"Stopped monitoring for deployment {deployment_id}")
            return True

        return False

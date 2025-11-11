"""Canary deployment controller for progressive rollouts."""

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from uuid import UUID, uuid4

from .cluster import ClusterConnection
from .deployments import DeploymentManager
from .health import DeploymentHealthChecker
from .models import DeploymentSpec

logger = logging.getLogger(__name__)


class CanaryPhase(str, Enum):
    """Canary deployment phase."""

    INITIALIZING = "initializing"
    CANARY_DEPLOYED = "canary_deployed"
    TRAFFIC_SHIFTING = "traffic_shifting"
    PROMOTING = "promoting"
    COMPLETED = "completed"
    ROLLING_BACK = "rolling_back"
    FAILED = "failed"


@dataclass
class CanaryConfig:
    """Canary deployment configuration."""

    canary_percentage: int = 10  # Initial canary traffic percentage
    increment_percentage: int = 10  # Traffic increment per step
    health_check_interval: int = 30  # Seconds between health checks
    analysis_duration: int = 180  # Seconds to analyze each step
    min_health_score: float = 0.8  # Minimum health score to proceed
    max_failures: int = 2  # Maximum consecutive health check failures


@dataclass
class CanaryDeployment:
    """Canary deployment state."""

    id: UUID
    name: str
    namespace: str
    stable_deployment: str
    canary_deployment: str
    current_percentage: int
    target_percentage: int
    phase: CanaryPhase
    config: CanaryConfig
    started_at: datetime
    completed_at: datetime | None = None
    health_scores: list[float] | None = None
    error_message: str | None = None


class CanaryDeploymentController:
    """
    Canary deployment controller for progressive rollouts.

    Implements canary deployment strategy:
    1. Deploy canary version alongside stable version
    2. Gradually shift traffic to canary
    3. Monitor health at each step
    4. Promote or rollback based on health
    """

    def __init__(self, cluster: ClusterConnection):
        """
        Initialize canary deployment controller.

        Args:
            cluster: Cluster connection
        """
        self.cluster = cluster
        self.deployment_manager = DeploymentManager(cluster)
        self.health_checker = DeploymentHealthChecker(cluster)

        # Track active canary deployments
        self._canary_deployments: dict[UUID, CanaryDeployment] = {}
        self._canary_tasks: dict[UUID, asyncio.Task] = {}

    async def start_canary_deployment(
        self,
        name: str,
        namespace: str,
        new_spec: DeploymentSpec,
        config: CanaryConfig | None = None,
    ) -> UUID:
        """
        Start a canary deployment.

        Args:
            name: Base deployment name
            namespace: Kubernetes namespace
            new_spec: New deployment specification for canary
            config: Canary configuration (uses defaults if not provided)

        Returns:
            Canary deployment ID
        """
        canary_id = uuid4()
        config = config or CanaryConfig()

        stable_name = f"{name}-stable"
        canary_name = f"{name}-canary"

        # Check if stable deployment exists
        stable_deployment = self.deployment_manager.get(stable_name, namespace)
        if not stable_deployment:
            # If no stable deployment, this is the first deployment
            # Create it directly without canary
            logger.info(f"No stable deployment found, creating {stable_name} directly")
            self.deployment_manager.create(new_spec)
            raise ValueError("No stable deployment exists yet")

        canary_deployment = CanaryDeployment(
            id=canary_id,
            name=name,
            namespace=namespace,
            stable_deployment=stable_name,
            canary_deployment=canary_name,
            current_percentage=0,
            target_percentage=100,
            phase=CanaryPhase.INITIALIZING,
            config=config,
            started_at=datetime.utcnow(),
            health_scores=[],
        )

        self._canary_deployments[canary_id] = canary_deployment

        # Start canary rollout task
        task = asyncio.create_task(
            self._canary_rollout_loop(canary_id, canary_deployment, new_spec)
        )
        self._canary_tasks[canary_id] = task

        logger.info(f"Started canary deployment {canary_id} for {name} in {namespace}")

        return canary_id

    async def _canary_rollout_loop(
        self,
        canary_id: UUID,
        canary: CanaryDeployment,
        new_spec: DeploymentSpec,
    ) -> None:
        """
        Execute canary rollout with progressive traffic shifting.

        Args:
            canary_id: Canary deployment ID
            canary: Canary deployment state
            new_spec: New deployment specification
        """
        try:
            # Step 1: Create canary deployment
            logger.info(f"Creating canary deployment {canary.canary_deployment}")
            await self._create_canary_deployment(canary, new_spec)
            canary.phase = CanaryPhase.CANARY_DEPLOYED

            # Step 2: Progressive traffic shifting
            canary.phase = CanaryPhase.TRAFFIC_SHIFTING

            while canary.current_percentage < canary.target_percentage:
                # Calculate next traffic percentage
                next_percentage = min(
                    canary.current_percentage + canary.config.increment_percentage,
                    canary.target_percentage,
                )

                logger.info(
                    f"Shifting traffic to {next_percentage}% canary "
                    f"(current: {canary.current_percentage}%)"
                )

                # Update traffic weights
                await self._update_traffic_split(canary, next_percentage)
                canary.current_percentage = next_percentage

                # Wait for analysis duration
                logger.info(f"Analyzing canary for {canary.config.analysis_duration}s")
                await asyncio.sleep(canary.config.analysis_duration)

                # Check canary health
                health_result = self.health_checker.check_deployment_health(
                    name=canary.canary_deployment,
                    namespace=canary.namespace,
                )

                canary.health_scores.append(health_result.score)

                logger.info(
                    f"Canary health: {health_result.status.value} "
                    f"(score: {health_result.score:.2f})"
                )

                # Check if health is acceptable
                if health_result.score < canary.config.min_health_score:
                    logger.warning(
                        f"Canary health score {health_result.score:.2f} "
                        f"below threshold {canary.config.min_health_score}"
                    )
                    # Trigger rollback
                    await self._rollback_canary(canary, health_result.message)
                    return

            # Step 3: Promote canary to stable
            logger.info("Canary passed all health checks, promoting to stable")
            canary.phase = CanaryPhase.PROMOTING
            await self._promote_canary(canary)

            canary.phase = CanaryPhase.COMPLETED
            canary.completed_at = datetime.utcnow()

            logger.info(f"Canary deployment {canary_id} completed successfully")

        except Exception as e:
            logger.error(f"Canary deployment {canary_id} failed: {e}", exc_info=True)
            canary.phase = CanaryPhase.FAILED
            canary.error_message = str(e)
            canary.completed_at = datetime.utcnow()
            raise

    async def _create_canary_deployment(
        self, canary: CanaryDeployment, new_spec: DeploymentSpec
    ) -> None:
        """
        Create canary deployment with initial traffic percentage.

        Args:
            canary: Canary deployment state
            new_spec: New deployment specification
        """
        # Calculate canary replicas based on percentage
        stable_deployment = self.deployment_manager.get(
            canary.stable_deployment, canary.namespace
        )
        if not stable_deployment:
            raise ValueError(f"Stable deployment {canary.stable_deployment} not found")

        stable_replicas = stable_deployment.spec.replicas or 1
        canary_replicas = max(
            1, int(stable_replicas * canary.config.canary_percentage / 100)
        )

        # Create canary deployment spec
        canary_spec = DeploymentSpec(
            name=canary.canary_deployment,
            namespace=canary.namespace,
            image=new_spec.image,
            replicas=canary_replicas,
            command=new_spec.command,
            args=new_spec.args,
            env=new_spec.env,
            resources=new_spec.resources,
            ports=new_spec.ports,
            labels={
                **new_spec.labels,
                "deployment-type": "canary",
                "canary-for": canary.stable_deployment,
            },
            annotations={
                **new_spec.annotations,
                "canary-id": str(canary.id),
            },
            volumes=new_spec.volumes,
            volume_mounts=new_spec.volume_mounts,
        )

        # Create canary deployment
        self.deployment_manager.create(canary_spec)

        logger.info(
            f"Created canary deployment {canary.canary_deployment} "
            f"with {canary_replicas} replicas"
        )

    async def _update_traffic_split(
        self, canary: CanaryDeployment, percentage: int
    ) -> None:
        """
        Update traffic split between stable and canary.

        Note: This would typically update a service mesh or ingress configuration.
        For now, this is a placeholder that scales replicas proportionally.

        Args:
            canary: Canary deployment state
            percentage: Percentage of traffic to send to canary (0-100)
        """
        # Get current stable deployment
        stable_deployment = self.deployment_manager.get(
            canary.stable_deployment, canary.namespace
        )
        if not stable_deployment:
            return

        total_replicas = stable_deployment.spec.replicas or 1

        # Calculate replica distribution
        canary_replicas = max(1, int(total_replicas * percentage / 100))
        stable_replicas = max(1, total_replicas - canary_replicas)

        # Scale deployments
        self.deployment_manager.scale(
            canary.stable_deployment, canary.namespace, stable_replicas
        )
        self.deployment_manager.scale(
            canary.canary_deployment, canary.namespace, canary_replicas
        )

        logger.info(
            f"Updated traffic split: {percentage}% canary "
            f"({canary_replicas} replicas), "
            f"{100-percentage}% stable ({stable_replicas} replicas)"
        )

    async def _promote_canary(self, canary: CanaryDeployment) -> None:
        """
        Promote canary to stable by replacing stable deployment.

        Args:
            canary: Canary deployment state
        """
        # Get canary deployment
        canary_deployment = self.deployment_manager.get(
            canary.canary_deployment, canary.namespace
        )
        if not canary_deployment:
            raise ValueError(f"Canary deployment {canary.canary_deployment} not found")

        # Update stable deployment with canary spec
        # This would copy the canary's image and configuration to stable
        logger.info(
            f"Promoting canary {canary.canary_deployment} "
            f"to stable {canary.stable_deployment}"
        )

        # Delete canary deployment
        self.deployment_manager.delete(canary.canary_deployment, canary.namespace)

        logger.info("Canary promotion completed")

    async def _rollback_canary(self, canary: CanaryDeployment, reason: str) -> None:
        """
        Rollback canary deployment due to health check failure.

        Args:
            canary: Canary deployment state
            reason: Rollback reason
        """
        logger.warning(f"Rolling back canary deployment: {reason}")
        canary.phase = CanaryPhase.ROLLING_BACK

        # Delete canary deployment
        try:
            self.deployment_manager.delete(canary.canary_deployment, canary.namespace)
        except Exception as e:
            logger.error(f"Error deleting canary deployment: {e}")

        # Restore stable to full capacity
        stable_deployment = self.deployment_manager.get(
            canary.stable_deployment, canary.namespace
        )
        if stable_deployment:
            original_replicas = stable_deployment.spec.replicas or 1
            self.deployment_manager.scale(
                canary.stable_deployment, canary.namespace, original_replicas
            )

        canary.phase = CanaryPhase.FAILED
        canary.error_message = f"Rollback triggered: {reason}"
        canary.completed_at = datetime.utcnow()

        logger.info("Canary rollback completed")

    def get_canary_status(self, canary_id: UUID) -> CanaryDeployment | None:
        """
        Get status of a canary deployment.

        Args:
            canary_id: Canary deployment ID

        Returns:
            CanaryDeployment or None if not found
        """
        return self._canary_deployments.get(canary_id)

    async def cancel_canary(self, canary_id: UUID) -> bool:
        """
        Cancel an in-progress canary deployment.

        Args:
            canary_id: Canary deployment ID

        Returns:
            True if cancelled, False if not found
        """
        task = self._canary_tasks.get(canary_id)
        canary = self._canary_deployments.get(canary_id)

        if task and canary:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

            await self._rollback_canary(canary, "Manually cancelled")

            logger.info(f"Cancelled canary deployment {canary_id}")
            return True

        return False

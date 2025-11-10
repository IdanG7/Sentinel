"""Pipeline Controller - Main orchestration logic."""

import asyncio
import json
import logging
from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from aiokafka import AIOKafkaConsumer, AIOKafkaProducer
from sentinel_k8s import ClusterConnection, ClusterManager, DeploymentManager
from sentinel_policy import ActionPlan, EvaluationMode, PolicyEngine

from .config import Settings
from .executors import DeploymentExecutor
from .health import HealthChecker

logger = logging.getLogger(__name__)


class PipelineController:
    """
    Pipeline Controller orchestrates deployment and action plan execution.

    Responsibilities:
    - Consume events from Kafka
    - Validate action plans with Policy Engine
    - Execute deployments to Kubernetes
    - Monitor health and trigger rollbacks
    """

    def __init__(self, settings: Settings):
        """
        Initialize pipeline controller.

        Args:
            settings: Application settings
        """
        self.settings = settings
        self._running = False

        # Initialize components
        self.policy_engine = PolicyEngine(
            mode=EvaluationMode(settings.policy_engine_mode)
        )
        self.cluster_manager: Optional[ClusterManager] = None
        self.consumer: Optional[AIOKafkaConsumer] = None
        self.producer: Optional[AIOKafkaProducer] = None
        self.deployment_executor: Optional[DeploymentExecutor] = None
        self.health_checker: Optional[HealthChecker] = None

        # Track active deployments
        self._active_deployments: dict[UUID, dict[str, Any]] = {}
        self._tasks: list[asyncio.Task] = []

    async def start(self) -> None:
        """Start the pipeline controller."""
        if self._running:
            logger.warning("Pipeline controller already running")
            return

        self._running = True

        # Initialize Kafka consumer
        self.consumer = AIOKafkaConsumer(
            self.settings.kafka_topic_deployments,
            self.settings.kafka_topic_action_plans,
            bootstrap_servers=self.settings.kafka_bootstrap_servers,
            group_id=self.settings.kafka_consumer_group,
            value_deserializer=lambda m: json.loads(m.decode("utf-8")),
        )
        await self.consumer.start()
        logger.info("✓ Kafka consumer started")

        # Initialize Kafka producer
        self.producer = AIOKafkaProducer(
            bootstrap_servers=self.settings.kafka_bootstrap_servers,
            value_serializer=lambda v: json.dumps(v).encode("utf-8"),
        )
        await self.producer.start()
        logger.info("✓ Kafka producer started")

        # Initialize Kubernetes cluster manager
        self.cluster_manager = ClusterManager()
        logger.info("✓ Cluster manager initialized")

        # Initialize executors
        self.deployment_executor = DeploymentExecutor(
            cluster_manager=self.cluster_manager,
            producer=self.producer,
            settings=self.settings,
        )
        logger.info("✓ Deployment executor initialized")

        # Initialize health checker
        self.health_checker = HealthChecker(
            cluster_manager=self.cluster_manager,
            settings=self.settings,
        )
        logger.info("✓ Health checker initialized")

        # Start consuming events
        consume_task = asyncio.create_task(self._consume_events())
        self._tasks.append(consume_task)

        # Start health checking
        health_task = asyncio.create_task(self._health_check_loop())
        self._tasks.append(health_task)

        logger.info("Pipeline controller started")

    async def stop(self) -> None:
        """Stop the pipeline controller."""
        logger.info("Stopping pipeline controller...")
        self._running = False

        # Cancel all tasks
        for task in self._tasks:
            task.cancel()

        # Wait for tasks to complete
        await asyncio.gather(*self._tasks, return_exceptions=True)
        self._tasks.clear()

        # Stop Kafka consumer and producer
        if self.consumer:
            await self.consumer.stop()
        if self.producer:
            await self.producer.stop()

        logger.info("Pipeline controller stopped")

    async def _consume_events(self) -> None:
        """Consume events from Kafka and process them."""
        logger.info("Starting event consumer...")

        try:
            async for message in self.consumer:
                if not self._running:
                    break

                try:
                    event = message.value
                    event_type = event.get("event_type")
                    data = event.get("data", {})

                    logger.debug(f"Received event: {event_type}")

                    # Route event to appropriate handler
                    if event_type == "deployment.created":
                        await self._handle_deployment_created(data)
                    elif event_type == "deployment.scaled":
                        await self._handle_deployment_scaled(data)
                    elif event_type == "deployment.rollback":
                        await self._handle_deployment_rollback(data)
                    elif event_type == "deployment.deleted":
                        await self._handle_deployment_deleted(data)
                    elif event_type == "action_plan.created":
                        await self._handle_action_plan_created(data)
                    else:
                        logger.debug(f"Unhandled event type: {event_type}")

                except Exception as e:
                    logger.error(f"Error processing event: {e}", exc_info=True)

        except asyncio.CancelledError:
            logger.info("Event consumer cancelled")
        except Exception as e:
            logger.error(f"Error in event consumer: {e}", exc_info=True)

    async def _handle_deployment_created(self, data: dict[str, Any]) -> None:
        """
        Handle deployment created event.

        Args:
            data: Deployment data
        """
        deployment_id = UUID(data["id"])
        logger.info(f"Handling deployment creation: {deployment_id}")

        # Track deployment
        self._active_deployments[deployment_id] = data

        # Execute deployment
        try:
            await self.deployment_executor.create_deployment(data)
            await self._publish_status_update(
                deployment_id, "running", "Deployment created successfully"
            )
        except Exception as e:
            logger.error(f"Failed to create deployment {deployment_id}: {e}")
            await self._publish_status_update(
                deployment_id, "failed", f"Deployment failed: {str(e)}"
            )

    async def _handle_deployment_scaled(self, data: dict[str, Any]) -> None:
        """
        Handle deployment scaled event.

        Args:
            data: Scale operation data
        """
        deployment_id = UUID(data["deployment_id"])
        new_replicas = data["new_replicas"]
        logger.info(f"Handling deployment scale: {deployment_id} -> {new_replicas} replicas")

        try:
            await self.deployment_executor.scale_deployment(deployment_id, new_replicas)
            await self._publish_status_update(
                deployment_id, "running", f"Scaled to {new_replicas} replicas"
            )
        except Exception as e:
            logger.error(f"Failed to scale deployment {deployment_id}: {e}")
            await self._publish_status_update(
                deployment_id, "failed", f"Scale failed: {str(e)}"
            )

    async def _handle_deployment_rollback(self, data: dict[str, Any]) -> None:
        """
        Handle deployment rollback event.

        Args:
            data: Rollback data
        """
        deployment_id = UUID(data["deployment_id"])
        logger.info(f"Handling deployment rollback: {deployment_id}")

        try:
            await self.deployment_executor.rollback_deployment(deployment_id)
            await self._publish_status_update(
                deployment_id, "rolled_back", "Deployment rolled back"
            )
        except Exception as e:
            logger.error(f"Failed to rollback deployment {deployment_id}: {e}")

    async def _handle_deployment_deleted(self, data: dict[str, Any]) -> None:
        """
        Handle deployment deleted event.

        Args:
            data: Deletion data
        """
        deployment_id = UUID(data["deployment_id"])
        logger.info(f"Handling deployment deletion: {deployment_id}")

        try:
            await self.deployment_executor.delete_deployment(deployment_id)
            # Remove from active deployments
            self._active_deployments.pop(deployment_id, None)
        except Exception as e:
            logger.error(f"Failed to delete deployment {deployment_id}: {e}")

    async def _handle_action_plan_created(self, data: dict[str, Any]) -> None:
        """
        Handle action plan created event.

        Args:
            data: Action plan data
        """
        plan_id = UUID(data["id"])
        logger.info(f"Handling action plan: {plan_id}")

        try:
            # Parse action plan
            action_plan = ActionPlan(
                id=plan_id,
                decisions=data["decisions"],
                source=data["source"],
                correlation_id=data.get("correlation_id"),
                created_at=datetime.fromisoformat(data["created_at"]),
            )

            # Validate with policy engine
            evaluation = self.policy_engine.evaluate(action_plan)

            if evaluation.approved:
                logger.info(f"Action plan {plan_id} approved, executing...")
                await self._execute_action_plan(action_plan)
                await self._publish_action_plan_status(plan_id, "completed")
            else:
                logger.warning(
                    f"Action plan {plan_id} rejected: {len(evaluation.violations)} violations"
                )
                await self._publish_action_plan_status(
                    plan_id,
                    "rejected",
                    violations=[v.model_dump() for v in evaluation.violations],
                )

        except Exception as e:
            logger.error(f"Error handling action plan {plan_id}: {e}", exc_info=True)
            await self._publish_action_plan_status(
                plan_id, "failed", error=str(e)
            )

    async def _execute_action_plan(self, action_plan: ActionPlan) -> None:
        """
        Execute an approved action plan.

        Args:
            action_plan: Action plan to execute
        """
        logger.info(f"Executing action plan {action_plan.id} with {len(action_plan.decisions)} decisions")

        for decision in action_plan.decisions:
            try:
                verb = decision.verb.value
                target = decision.target
                params = decision.params

                logger.info(f"Executing decision: {verb} on {target}")

                # Route to appropriate executor based on verb
                if verb == "scale":
                    await self.deployment_executor.execute_scale_decision(decision)
                elif verb == "reschedule":
                    await self.deployment_executor.execute_reschedule_decision(decision)
                elif verb == "rollback":
                    await self.deployment_executor.execute_rollback_decision(decision)
                elif verb == "restart":
                    await self.deployment_executor.execute_restart_decision(decision)
                elif verb == "drain":
                    await self.deployment_executor.execute_drain_decision(decision)
                else:
                    logger.warning(f"Unknown decision verb: {verb}")

            except Exception as e:
                logger.error(f"Error executing decision {decision.verb}: {e}", exc_info=True)
                # Continue with other decisions even if one fails

    async def _health_check_loop(self) -> None:
        """Periodically check health of active deployments."""
        logger.info("Starting health check loop...")

        try:
            while self._running:
                await asyncio.sleep(self.settings.health_check_interval_seconds)

                if not self._active_deployments:
                    continue

                logger.debug(f"Running health checks on {len(self._active_deployments)} deployments")

                for deployment_id, deployment_data in list(self._active_deployments.items()):
                    try:
                        is_healthy = await self.health_checker.check_deployment_health(
                            deployment_id, deployment_data
                        )

                        if not is_healthy and self.settings.auto_rollback_enabled:
                            logger.warning(f"Deployment {deployment_id} unhealthy, triggering rollback")
                            await self._handle_deployment_rollback({"deployment_id": str(deployment_id)})

                    except Exception as e:
                        logger.error(f"Error checking health for {deployment_id}: {e}")

        except asyncio.CancelledError:
            logger.info("Health check loop cancelled")
        except Exception as e:
            logger.error(f"Error in health check loop: {e}", exc_info=True)

    async def _publish_status_update(
        self, deployment_id: UUID, status: str, message: str
    ) -> None:
        """
        Publish deployment status update to Kafka.

        Args:
            deployment_id: Deployment UUID
            status: New status
            message: Status message
        """
        event = {
            "event_type": "deployment.status_updated",
            "timestamp": datetime.utcnow().isoformat(),
            "data": {
                "deployment_id": str(deployment_id),
                "status": status,
                "message": message,
            },
        }

        await self.producer.send(self.settings.kafka_topic_events, value=event)

    async def _publish_action_plan_status(
        self,
        plan_id: UUID,
        status: str,
        violations: Optional[list[dict]] = None,
        error: Optional[str] = None,
    ) -> None:
        """
        Publish action plan status update to Kafka.

        Args:
            plan_id: Action plan UUID
            status: New status
            violations: Optional policy violations
            error: Optional error message
        """
        event = {
            "event_type": "action_plan.status_updated",
            "timestamp": datetime.utcnow().isoformat(),
            "data": {
                "plan_id": str(plan_id),
                "status": status,
                "violations": violations,
                "error": error,
            },
        }

        await self.producer.send(self.settings.kafka_topic_events, value=event)

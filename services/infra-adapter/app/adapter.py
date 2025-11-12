"""InfraMind Adapter - Main orchestration logic."""

import asyncio
import json
import logging
from datetime import datetime
from typing import Any

import httpx
from aiokafka import AIOKafkaConsumer

from .config import Settings
from .grpc_client import InfraMindClient
from .inframind_client import InfraMindDecisionClient
from .telemetry import TelemetryCollector

logger = logging.getLogger(__name__)


class InfraMindAdapter:
    """
    InfraMind Adapter bridges Sentinel and InfraMind.

    Responsibilities:
    - Collect telemetry from Prometheus and Kafka
    - Stream telemetry batches to InfraMind
    - Receive action plans from InfraMind
    - Forward action plans to Control API
    """

    def __init__(self, settings: Settings):
        """
        Initialize InfraMind adapter.

        Args:
            settings: Application settings
        """
        self.settings = settings
        self._running = False

        # Initialize components
        self.telemetry_collector = TelemetryCollector(settings)
        self.grpc_client = InfraMindClient(settings)
        self.inframind_brain = InfraMindDecisionClient(
            base_url=settings.inframind_api_url,
            api_key=settings.inframind_api_key if settings.inframind_api_key else None,
        )
        self.consumer: AIOKafkaConsumer | None = None
        self.http_client: httpx.AsyncClient | None = None

        # Batching state
        self._telemetry_batch: list[dict[str, Any]] = []
        self._last_batch_time = datetime.utcnow()
        self._tasks: list[asyncio.Task] = []

    async def start(self) -> None:
        """Start the adapter."""
        if self._running:
            logger.warning("Adapter already running")
            return

        self._running = True

        # Initialize HTTP client for Control API
        self.http_client = httpx.AsyncClient(
            base_url=self.settings.control_api_url,
            timeout=30.0,
        )
        logger.info("✓ HTTP client initialized")

        # Initialize InfraMind Decision Brain (REST API)
        if self.settings.inframind_api_enabled:
            try:
                await self.inframind_brain.connect()
                logger.info("✓ InfraMind Decision Brain connected")
            except Exception as e:
                logger.warning(f"Could not connect to InfraMind Brain: {e}")
                logger.info("Continuing without InfraMind Brain (will use fallback logic)")

        # Initialize gRPC client to InfraMind (legacy)
        try:
            await self.grpc_client.connect()
        except Exception as e:
            logger.warning(f"Could not connect to InfraMind gRPC: {e}")
            logger.info("Continuing without InfraMind gRPC connection")

        # Initialize Kafka consumer for events
        self.consumer = AIOKafkaConsumer(
            self.settings.kafka_topic_events,
            self.settings.kafka_topic_deployments,
            bootstrap_servers=self.settings.kafka_bootstrap_servers,
            group_id=self.settings.kafka_consumer_group,
            value_deserializer=lambda m: json.loads(m.decode("utf-8")),
        )
        await self.consumer.start()
        logger.info("✓ Kafka consumer started")

        # Start background tasks
        telemetry_task = asyncio.create_task(self._telemetry_collection_loop())
        self._tasks.append(telemetry_task)

        event_task = asyncio.create_task(self._event_collection_loop())
        self._tasks.append(event_task)

        # Start InfraMind Brain decision loop (actively requests optimizations)
        if self.settings.inframind_api_enabled:
            decision_task = asyncio.create_task(self._inframind_decision_loop())
            self._tasks.append(decision_task)

        # Start action plan receiver from InfraMind gRPC (legacy)
        if self.grpc_client.connected:
            action_plan_task = asyncio.create_task(self._receive_action_plans())
            self._tasks.append(action_plan_task)
        else:
            logger.warning("Skipping gRPC action plan receiver (not connected)")

        logger.info("Adapter started")

    async def stop(self) -> None:
        """Stop the adapter."""
        logger.info("Stopping adapter...")
        self._running = False

        # Cancel all tasks
        for task in self._tasks:
            task.cancel()

        # Wait for tasks to complete
        await asyncio.gather(*self._tasks, return_exceptions=True)
        self._tasks.clear()

        # Close connections
        if self.consumer:
            await self.consumer.stop()

        if self.http_client:
            await self.http_client.aclose()

        # Disconnect from InfraMind
        await self.grpc_client.disconnect()
        await self.inframind_brain.disconnect()

        logger.info("Adapter stopped")

    async def _telemetry_collection_loop(self) -> None:
        """Periodically collect telemetry from Prometheus."""
        logger.info("Starting telemetry collection loop...")

        try:
            while self._running:
                await asyncio.sleep(self.settings.telemetry_batch_interval_seconds)

                try:
                    # Collect telemetry from Prometheus
                    telemetry = await self.telemetry_collector.collect()

                    if telemetry:
                        logger.debug(f"Collected {len(telemetry)} telemetry points")
                        self._telemetry_batch.extend(telemetry)

                    # Check if we should send batch
                    await self._check_and_send_batch()

                except Exception as e:
                    logger.error(f"Error collecting telemetry: {e}", exc_info=True)

        except asyncio.CancelledError:
            logger.info("Telemetry collection loop cancelled")
        except Exception as e:
            logger.error(f"Error in telemetry collection loop: {e}", exc_info=True)

    async def _event_collection_loop(self) -> None:
        """Collect events from Kafka and add to telemetry batch."""
        logger.info("Starting event collection loop...")

        if not self.consumer:
            logger.error("Consumer not initialized, cannot start event collection loop")
            return

        try:
            async for message in self.consumer:
                if not self._running:
                    break

                try:
                    event = message.value
                    event_type = event.get("event_type")

                    # Add event to telemetry batch
                    telemetry_point = {
                        "timestamp": event.get("timestamp", datetime.utcnow().isoformat()),
                        "type": "event",
                        "event_type": event_type,
                        "data": event.get("data", {}),
                    }

                    self._telemetry_batch.append(telemetry_point)
                    logger.debug(f"Added event to batch: {event_type}")

                    # Check if we should send batch
                    await self._check_and_send_batch()

                except Exception as e:
                    logger.error(f"Error processing event: {e}", exc_info=True)

        except asyncio.CancelledError:
            logger.info("Event collection loop cancelled")
        except Exception as e:
            logger.error(f"Error in event collection loop: {e}", exc_info=True)

    async def _check_and_send_batch(self) -> None:
        """Check if batch should be sent and send if needed."""
        batch_age = (datetime.utcnow() - self._last_batch_time).total_seconds()

        should_send = (
            len(self._telemetry_batch) >= self.settings.max_batch_size
            or batch_age >= self.settings.max_batch_age_seconds
        )

        if should_send and self._telemetry_batch:
            await self._send_telemetry_batch()

    async def _send_telemetry_batch(self) -> None:
        """Send telemetry batch to InfraMind."""
        if not self._telemetry_batch:
            return

        batch_size = len(self._telemetry_batch)
        logger.info(f"Sending telemetry batch of {batch_size} points to InfraMind")

        try:
            # Send telemetry to InfraMind Brain (REST API) - PRIMARY METHOD
            if self.settings.inframind_api_enabled:
                try:
                    result = await self.inframind_brain.send_telemetry(self._telemetry_batch)
                    logger.info(f"✓ Sent {batch_size} telemetry points to InfraMind Brain")
                    # Clear batch on success
                    self._telemetry_batch.clear()
                    self._last_batch_time = datetime.utcnow()
                    return
                except Exception as e:
                    logger.warning(f"Failed to send to InfraMind Brain: {e}")
                    # Fall through to gRPC fallback

            # Send telemetry via gRPC (fallback/legacy)
            if self.grpc_client.connected:
                ack = await self.grpc_client.send_telemetry_batch(self._telemetry_batch)
                if ack.success:
                    logger.info(f"✓ Sent {batch_size} telemetry points via gRPC: {ack.message}")
                    # Clear batch on success
                    self._telemetry_batch.clear()
                    self._last_batch_time = datetime.utcnow()
                else:
                    logger.error(f"Failed to send telemetry: {ack.message}")
                    # Keep batch for retry
            else:
                logger.warning("Not connected to any InfraMind endpoint, keeping batch for retry")

        except Exception as e:
            logger.error(f"Error sending telemetry batch: {e}", exc_info=True)
            # Keep batch for retry

    async def _inframind_decision_loop(self) -> None:
        """
        Periodically request optimization decisions from InfraMind Brain.

        This is the KEY integration point where InfraMind's intelligence
        is applied to generate action plans for Sentinel.
        """
        logger.info("Starting InfraMind decision loop...")

        # Poll interval - how often to ask InfraMind for optimization suggestions
        decision_interval_seconds = 300  # 5 minutes

        try:
            while self._running:
                await asyncio.sleep(decision_interval_seconds)

                try:
                    # Get current cluster context for InfraMind
                    context = await self._build_decision_context()

                    # Ask InfraMind Brain for optimization suggestions
                    logger.info("Requesting optimization suggestions from InfraMind Brain...")
                    decisions = await self.inframind_brain.get_optimization_suggestions(
                        cluster_id=self.settings.service_name,
                        context=context,
                    )

                    if decisions:
                        logger.info(
                            f"✓ InfraMind Brain provided {len(decisions)} optimization decisions"
                        )

                        # Convert InfraMind decisions to Sentinel action plan
                        action_plan = self._convert_to_action_plan(decisions)

                        # Forward to Control API
                        await self._submit_action_plan_to_control_api(action_plan)

                    else:
                        logger.debug("No optimization suggestions from InfraMind at this time")

                except Exception as e:
                    logger.error(f"Error in InfraMind decision loop: {e}", exc_info=True)
                    # Continue running even if one iteration fails

        except asyncio.CancelledError:
            logger.info("InfraMind decision loop cancelled")
        except Exception as e:
            logger.error(f"Fatal error in InfraMind decision loop: {e}", exc_info=True)

    async def _build_decision_context(self) -> dict[str, Any]:
        """
        Build context information for InfraMind decision-making.

        Returns:
            Dictionary with current state, metrics, and workload info
        """
        # TODO: Fetch real cluster state from Control API or Prometheus
        # For now, return minimal context
        context = {
            "timestamp": datetime.utcnow().isoformat(),
            "cluster_id": self.settings.service_name,
            "telemetry_batch_size": len(self._telemetry_batch),
        }

        # Try to get workload summary from Control API
        if self.http_client:
            try:
                response = await self.http_client.get("/workloads")
                if response.status_code == 200:
                    workloads = response.json()
                    context["workload_count"] = len(workloads)
                    context["workloads"] = workloads[:10]  # Send summary of first 10
            except Exception as e:
                logger.debug(f"Could not fetch workloads for context: {e}")

        return context

    def _convert_to_action_plan(self, decisions: list[dict[str, Any]]) -> dict[str, Any]:
        """
        Convert InfraMind decisions to Sentinel action plan format.

        Args:
            decisions: List of decisions from InfraMind

        Returns:
            Action plan in Sentinel format
        """
        import uuid

        plan_id = str(uuid.uuid4())

        # Convert InfraMind decision format to Sentinel decision format
        sentinel_decisions = []
        for decision in decisions:
            sentinel_decision = {
                "verb": decision.get("action", "scale"),  # e.g., scale, restart, migrate
                "target": decision.get("target", {}),      # Resource to act on
                "params": decision.get("params", {}),      # Action parameters
                "ttl": decision.get("ttl", 3600),          # Time to live
                "safety": decision.get("safety"),          # Safety constraints
            }
            sentinel_decisions.append(sentinel_decision)

        action_plan = {
            "plan_id": plan_id,
            "source": "inframind-brain",
            "decisions": sentinel_decisions,
            "created_at": datetime.utcnow().isoformat(),
            "correlation_id": plan_id,
        }

        return action_plan

    async def _submit_action_plan_to_control_api(self, action_plan: dict[str, Any]) -> None:
        """
        Submit action plan to Control API for execution.

        Args:
            action_plan: Action plan from InfraMind
        """
        if not self.http_client:
            logger.error("HTTP client not initialized")
            return

        plan_id = action_plan.get("plan_id")
        logger.info(f"Submitting action plan {plan_id} to Control API")

        try:
            response = await self.http_client.post(
                "/action-plans",
                json=action_plan,
                headers=(
                    {"Authorization": f"Bearer {self.settings.control_api_token}"}
                    if self.settings.control_api_token
                    else {}
                ),
            )

            response.raise_for_status()
            logger.info(f"✓ Action plan {plan_id} submitted successfully to Control API")

            # Report success back to InfraMind for learning
            await self.inframind_brain.report_execution_outcome(
                plan_id=plan_id,
                success=True,
                metrics={"submitted_at": datetime.utcnow().isoformat()},
            )

        except httpx.HTTPError as e:
            logger.error(f"Failed to submit action plan to Control API: {e}")

            # Report failure to InfraMind
            await self.inframind_brain.report_execution_outcome(
                plan_id=plan_id,
                success=False,
                metrics={"error": str(e)},
            )

    async def _receive_action_plans(self) -> None:
        """
        Receive action plans from InfraMind via gRPC streaming.

        Action plans are streamed from InfraMind and forwarded to Control API.
        """
        logger.info("Starting action plan receiver...")

        try:
            cluster_id = self.settings.service_name

            async for action_plan in self.grpc_client.stream_action_plans(cluster_id):
                if not self._running:
                    break

                logger.info(
                    f"Received action plan {action_plan.plan_id} "
                    f"with {len(action_plan.decisions)} decisions"
                )

                try:
                    # Forward plan to Control API
                    await self._forward_action_plan(action_plan)

                    # Acknowledge successful processing
                    await self.grpc_client.acknowledge_plan(
                        plan_id=action_plan.plan_id,
                        success=True,
                        message="Plan forwarded to Control API",
                    )

                except Exception as e:
                    logger.error(f"Error processing action plan: {e}", exc_info=True)

                    # Acknowledge failure
                    await self.grpc_client.acknowledge_plan(
                        plan_id=action_plan.plan_id,
                        success=False,
                        message=str(e),
                    )

        except asyncio.CancelledError:
            logger.info("Action plan receiver cancelled")
        except Exception as e:
            logger.error(f"Error receiving action plans: {e}", exc_info=True)

    async def _forward_action_plan(self, action_plan: Any) -> None:
        """
        Forward an action plan from InfraMind to Control API.

        Args:
            action_plan: ActionPlan proto message from InfraMind
        """
        if not self.http_client:
            logger.error("HTTP client not initialized, cannot forward action plan")
            raise RuntimeError("HTTP client not initialized")

        logger.info(f"Forwarding action plan {action_plan.plan_id} to Control API")

        # Convert proto to dict for HTTP API
        plan_dict = {
            "plan_id": action_plan.plan_id,
            "source": action_plan.source or "inframind",
            "decisions": [
                {
                    "verb": d.verb,
                    "target": dict(d.target),
                    "params": dict(d.params),
                    "ttl": d.ttl,
                    "safety": (
                        {
                            "rate_limit": d.safety.rate_limit,
                            "window": d.safety.window,
                        }
                        if d.safety
                        else None
                    ),
                }
                for d in action_plan.decisions
            ],
            "created_at": action_plan.created_at,
            "correlation_id": action_plan.correlation_id,
        }

        try:
            response = await self.http_client.post(
                "/action-plans",
                json=plan_dict,
                headers=(
                    {"Authorization": f"Bearer {self.settings.control_api_token}"}
                    if self.settings.control_api_token
                    else {}
                ),
            )

            response.raise_for_status()
            logger.info(f"✓ Action plan {action_plan.plan_id} forwarded successfully")

        except httpx.HTTPError as e:
            logger.error(f"Error forwarding action plan: {e}", exc_info=True)
            raise

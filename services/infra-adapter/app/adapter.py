"""InfraMind Adapter - Main orchestration logic."""

import asyncio
import json
import logging
from datetime import datetime, timedelta
from typing import Any, Optional

import grpc
import httpx
from aiokafka import AIOKafkaConsumer

from .config import Settings
from .grpc_client import InfraMindClient
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
        self.consumer: Optional[AIOKafkaConsumer] = None
        self.http_client: Optional[httpx.AsyncClient] = None

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

        # Initialize gRPC client to InfraMind
        try:
            await self.grpc_client.connect()
        except Exception as e:
            logger.warning(f"Could not connect to InfraMind: {e}")
            logger.info("Continuing without InfraMind connection (will retry later)")

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

        # Start action plan receiver from InfraMind
        if self.grpc_client.connected:
            action_plan_task = asyncio.create_task(self._receive_action_plans())
            self._tasks.append(action_plan_task)
        else:
            logger.warning("Skipping action plan receiver (not connected to InfraMind)")

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
            # Send telemetry via gRPC
            if self.grpc_client.connected:
                ack = await self.grpc_client.send_telemetry_batch(self._telemetry_batch)
                if ack.success:
                    logger.info(f"✓ Sent {batch_size} telemetry points: {ack.message}")
                    # Clear batch on success
                    self._telemetry_batch.clear()
                    self._last_batch_time = datetime.utcnow()
                else:
                    logger.error(f"Failed to send telemetry: {ack.message}")
                    # Keep batch for retry
            else:
                logger.warning("Not connected to InfraMind, keeping batch for retry")
                # Try to reconnect
                try:
                    await self.grpc_client.connect()
                except Exception as e:
                    logger.debug(f"Reconnection failed: {e}")

        except Exception as e:
            logger.error(f"Error sending telemetry batch: {e}", exc_info=True)
            # Keep batch for retry

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

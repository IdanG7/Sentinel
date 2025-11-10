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
        self.consumer: Optional[AIOKafkaConsumer] = None
        self.http_client: Optional[httpx.AsyncClient] = None
        self.grpc_channel: Optional[grpc.aio.Channel] = None

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

        # Initialize gRPC channel to InfraMind
        if self.settings.inframind_tls_enabled:
            # Load TLS credentials
            with open(self.settings.inframind_tls_cert_path, 'rb') as f:
                credentials = grpc.ssl_channel_credentials(f.read())
            self.grpc_channel = grpc.aio.secure_channel(
                self.settings.inframind_url, credentials
            )
        else:
            self.grpc_channel = grpc.aio.insecure_channel(
                self.settings.inframind_url
            )
        logger.info("✓ gRPC channel initialized")

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

        # TODO: Start action plan receiver from InfraMind
        # action_plan_task = asyncio.create_task(self._receive_action_plans())
        # self._tasks.append(action_plan_task)

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

        if self.grpc_channel:
            await self.grpc_channel.close()

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
            # TODO: Implement gRPC call to InfraMind TelemetryIngestor
            # For now, just log the batch
            logger.debug(f"Telemetry batch: {self._telemetry_batch[:5]}...")  # Log first 5

            # Clear batch
            self._telemetry_batch.clear()
            self._last_batch_time = datetime.utcnow()

            logger.info(f"✓ Sent {batch_size} telemetry points")

        except Exception as e:
            logger.error(f"Error sending telemetry batch: {e}", exc_info=True)
            # Keep batch for retry
            pass

    async def _receive_action_plans(self) -> None:
        """
        Receive action plans from InfraMind via gRPC streaming.

        This is a placeholder for Phase 2 when InfraMind integration is complete.
        """
        logger.info("Starting action plan receiver...")

        try:
            # TODO: Implement gRPC streaming call to InfraMind DecisionAPI
            # For now, this is a placeholder
            while self._running:
                await asyncio.sleep(10)
                # Will implement in Phase 2
                pass

        except asyncio.CancelledError:
            logger.info("Action plan receiver cancelled")
        except Exception as e:
            logger.error(f"Error receiving action plans: {e}", exc_info=True)

    async def forward_action_plan_to_control_api(
        self, action_plan: dict[str, Any]
    ) -> None:
        """
        Forward an action plan from InfraMind to Control API.

        Args:
            action_plan: Action plan from InfraMind
        """
        logger.info(f"Forwarding action plan to Control API")

        try:
            response = await self.http_client.post(
                "/action-plans",
                json=action_plan,
                headers={"Authorization": f"Bearer {self.settings.control_api_token}"}
                if self.settings.control_api_token
                else {},
            )

            response.raise_for_status()
            logger.info(f"✓ Action plan forwarded successfully: {response.json()}")

        except httpx.HTTPError as e:
            logger.error(f"Error forwarding action plan: {e}", exc_info=True)
            raise

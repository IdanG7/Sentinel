"""gRPC client for InfraMind communication."""

import asyncio
import logging
import uuid
from collections.abc import AsyncIterator
from datetime import datetime
from typing import Any

import grpc

from .config import Settings
from .proto import (
    Ack,
    ActionPlan,
    TelemetryBatch,
    TelemetryPoint,
)

logger = logging.getLogger(__name__)


class InfraMindClient:
    """
    gRPC client for communicating with InfraMind.

    Handles:
    - Streaming telemetry data to InfraMind
    - Receiving action plans from InfraMind
    - Acknowledging plan execution
    """

    def __init__(self, settings: Settings):
        """
        Initialize InfraMind gRPC client.

        Args:
            settings: Application settings
        """
        self.settings = settings
        self.channel: grpc.aio.Channel | None = None
        self.connected = False

    async def connect(self) -> None:
        """Establish gRPC connection to InfraMind with mTLS."""
        if self.connected:
            logger.warning("Already connected to InfraMind")
            return

        try:
            if self.settings.inframind_tls_enabled:
                # Load mTLS credentials (client certificate + server CA)
                try:
                    from sentinel_common.mtls import (
                        create_grpc_channel_credentials,
                        mtls_config_from_env,
                    )

                    mtls_config = mtls_config_from_env(verify_server=True)
                    credentials = create_grpc_channel_credentials(mtls_config)

                    logger.info("Using mTLS for InfraMind connection")
                    self.channel = grpc.aio.secure_channel(
                        self.settings.inframind_url, credentials
                    )
                except (ImportError, FileNotFoundError) as e:
                    # Fallback to basic TLS if mTLS certs not available
                    logger.warning(
                        f"mTLS not available ({e}), falling back to basic TLS"
                    )
                    with open(self.settings.inframind_tls_cert_path, "rb") as f:
                        credentials = grpc.ssl_channel_credentials(f.read())
                    self.channel = grpc.aio.secure_channel(
                        self.settings.inframind_url, credentials
                    )
            else:
                logger.warning(
                    "Insecure connection to InfraMind (not recommended for production)"
                )
                self.channel = grpc.aio.insecure_channel(self.settings.inframind_url)

            # Test connection with a simple health check
            await self.channel.channel_ready()
            self.connected = True
            logger.info(f"✓ Connected to InfraMind at {self.settings.inframind_url}")

        except Exception as e:
            logger.error(f"Failed to connect to InfraMind: {e}", exc_info=True)
            self.connected = False
            raise

    async def disconnect(self) -> None:
        """Close gRPC connection."""
        if self.channel:
            await self.channel.close()
            self.connected = False
            logger.info("Disconnected from InfraMind")

    async def stream_telemetry(
        self, telemetry_iterator: AsyncIterator[TelemetryBatch]
    ) -> Ack:
        """
        Stream telemetry batches to InfraMind.

        Args:
            telemetry_iterator: Async iterator of telemetry batches

        Returns:
            Acknowledgment from InfraMind

        Note:
            This is a mock implementation for Phase 2 development.
            In production, this would use proper gRPC streaming.
        """
        if not self.connected:
            raise RuntimeError("Not connected to InfraMind")

        logger.info("Streaming telemetry to InfraMind...")

        try:
            batch_count = 0
            point_count = 0

            async for batch in telemetry_iterator:
                batch_count += 1
                point_count += len(batch.points)

                # In production, send via gRPC:
                # await stub.SubmitTelemetry(batch)

                # For now, just log
                logger.debug(f"Sent batch {batch.batch_id}: {len(batch.points)} points")

            logger.info(
                f"✓ Streamed {batch_count} batches ({point_count} points) to InfraMind"
            )

            return Ack(success=True, message=f"Received {point_count} telemetry points")

        except Exception as e:
            logger.error(f"Error streaming telemetry: {e}", exc_info=True)
            return Ack(success=False, message=str(e))

    async def send_telemetry_batch(self, telemetry_data: list[dict[str, Any]]) -> Ack:
        """
        Send a single telemetry batch to InfraMind.

        Args:
            telemetry_data: List of telemetry dictionaries

        Returns:
            Acknowledgment from InfraMind
        """
        if not telemetry_data:
            return Ack(success=True, message="Empty batch, nothing to send")

        # Convert dict to protobuf format
        points = []
        for item in telemetry_data:
            point = TelemetryPoint(
                name=item.get("metric_name", item.get("event_type", "unknown")),
                value=float(item.get("value", 0.0)),
                labels=item.get("labels", {}),
                ts=int(
                    datetime.fromisoformat(
                        item.get("timestamp", datetime.utcnow().isoformat())
                    ).timestamp()
                    * 1000
                ),
            )
            points.append(point)

        batch = TelemetryBatch(
            points=points,
            cluster_id=self.settings.service_name,
            batch_id=str(uuid.uuid4()),
        )

        # Mock implementation - in production would use gRPC
        logger.info(
            f"Sending telemetry batch {batch.batch_id} with {len(points)} points"
        )

        # Simulate network delay
        await asyncio.sleep(0.1)

        return Ack(
            success=True,
            message=f"Received batch {batch.batch_id} with {len(points)} points",
        )

    async def stream_action_plans(
        self, cluster_id: str, filters: list[str] | None = None
    ) -> AsyncIterator[ActionPlan]:
        """
        Stream action plans from InfraMind.

        Args:
            cluster_id: Cluster identifier
            filters: Optional filters for plan types

        Yields:
            Action plans from InfraMind

        Note:
            This is a mock implementation for Phase 2 development.
            In production, this would use proper gRPC streaming.
        """
        if False:
            # This yield is never executed but makes this function an async generator
            yield  # type: ignore[misc,unreachable]

        if not self.connected:
            raise RuntimeError("Not connected to InfraMind")

        logger.info(f"Streaming action plans for cluster {cluster_id}...")

        try:
            # In production, receive via gRPC:
            # stub = DecisionServiceStub(self.channel)
            # async for plan in stub.StreamActionPlans(request):
            #     yield plan

            # Mock implementation - simulate receiving plans
            while self.connected:
                # Wait for plans (in production, this would be server-streaming)
                await asyncio.sleep(10)

                # This is where real plans would arrive
                # For now, we don't yield anything in the mock
                # Actual implementation will be integrated when InfraMind is ready

        except grpc.aio.AioRpcError as e:
            logger.error(f"gRPC error streaming action plans: {e}", exc_info=True)
            raise
        except Exception as e:
            logger.error(f"Error streaming action plans: {e}", exc_info=True)
            raise

    async def acknowledge_plan(
        self,
        plan_id: str,
        success: bool,
        message: str = "",
        metrics: dict[str, str] | None = None,
    ) -> Ack:
        """
        Acknowledge plan execution to InfraMind.

        Args:
            plan_id: Plan identifier
            success: Whether execution was successful
            message: Execution result or error message
            metrics: Optional execution metrics

        Returns:
            Acknowledgment from InfraMind
        """
        if not self.connected:
            raise RuntimeError("Not connected to InfraMind")

        logger.info(
            f"Acknowledging plan {plan_id}: {'success' if success else 'failure'}"
        )

        try:
            # In production, send via gRPC:
            # stub = DecisionServiceStub(self.channel)
            # response = await stub.AckPlan(ack)

            # Mock implementation
            await asyncio.sleep(0.05)
            response = Ack(success=True, message=f"Plan {plan_id} acknowledged")

            logger.info(f"✓ Plan {plan_id} acknowledged by InfraMind")
            return response

        except Exception as e:
            logger.error(f"Error acknowledging plan: {e}", exc_info=True)
            return Ack(success=False, message=str(e))

"""Tests for infra-adapter."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.config import Settings


class TestInfraMindAdapter:
    """Test cases for InfraMind Adapter."""

    @pytest.fixture
    def settings(self):
        """Create test settings."""
        return Settings(
            inframind_url="localhost:50051",
            prometheus_url="http://localhost:9090",
            kafka_bootstrap_servers="localhost:9094",
            control_api_url="http://localhost:8000/api/v1",
        )

    def test_adapter_initialization(self, settings):
        """Test adapter can be initialized."""
        from app.adapter import InfraMindAdapter

        adapter = InfraMindAdapter(settings)

        assert adapter is not None
        assert adapter.settings == settings
        assert not adapter._running
        assert len(adapter._telemetry_batch) == 0

    @pytest.mark.asyncio
    async def test_telemetry_collector(self, settings):
        """Test telemetry collector can collect from Prometheus."""
        from app.telemetry import TelemetryCollector

        collector = TelemetryCollector(settings)

        # Mock httpx client
        with patch("httpx.AsyncClient") as mock_client:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "status": "success",
                "data": {
                    "result": [
                        {
                            "metric": {"node": "node-01"},
                            "value": [1234567890, "75.5"],
                        }
                    ]
                },
            }

            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                return_value=mock_response
            )

            telemetry = await collector.collect()

            assert len(telemetry) > 0
            # Verify telemetry structure
            if telemetry:
                point = telemetry[0]
                assert "timestamp" in point
                assert "type" in point
                assert point["type"] == "metric"

    @pytest.mark.asyncio
    async def test_grpc_client_connection(self, settings):
        """Test gRPC client can connect."""
        from app.grpc_client import InfraMindClient

        client = InfraMindClient(settings)

        with patch("grpc.aio.insecure_channel") as mock_channel:
            mock_channel.return_value.channel_ready = AsyncMock()

            await client.connect()

            assert client.connected
            mock_channel.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_telemetry_batch(self, settings):
        """Test sending telemetry batch to InfraMind."""
        from datetime import datetime

        from app.grpc_client import InfraMindClient

        client = InfraMindClient(settings)
        client.connected = True

        batch = [
            {
                "metric_name": "test_metric",
                "value": 100.0,
                "labels": {"node": "test"},
                "timestamp": datetime.utcnow().isoformat(),
            }
        ]

        ack = await client.send_telemetry_batch(batch)

        assert ack.success

    @pytest.mark.asyncio
    async def test_proto_classes(self):
        """Test proto classes can be instantiated."""
        from app.proto import ActionPlan, Decision, TelemetryBatch, TelemetryPoint

        # Test TelemetryPoint
        point = TelemetryPoint(
            name="cpu_usage", value=75.0, labels={"node": "node-01"}, ts=1234567890
        )
        assert point.name == "cpu_usage"
        assert point.value == 75.0

        # Test TelemetryBatch
        batch = TelemetryBatch(
            points=[point], cluster_id="test-cluster", batch_id="batch-123"
        )
        assert len(batch.points) == 1
        assert batch.cluster_id == "test-cluster"

        # Test Decision
        decision = Decision(
            verb="scale", target={"workload": "test"}, params={"replicas": "5"}, ttl=900
        )
        assert decision.verb == "scale"

        # Test ActionPlan
        plan = ActionPlan(
            plan_id="plan-123",
            decisions=[decision],
            source="inframind",
            created_at=1234567890,
        )
        assert plan.plan_id == "plan-123"
        assert len(plan.decisions) == 1

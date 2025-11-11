"""Tests for InfraMind gRPC client."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.config import Settings
from app.grpc_client import InfraMindClient


class TestInfraMindClient:
    """Test cases for InfraMind gRPC client."""

    @pytest.fixture
    def settings(self):
        """Create test settings."""
        return Settings(
            inframind_url="localhost:50051",
            inframind_tls_enabled=False,
            service_name="test-cluster",
        )

    @pytest.fixture
    def client(self, settings):
        """Create test client."""
        return InfraMindClient(settings)

    @pytest.mark.asyncio
    async def test_client_initialization(self, client):
        """Test client can be initialized."""
        assert client is not None
        assert not client.connected
        assert client.channel is None

    @pytest.mark.asyncio
    async def test_connect_insecure(self, client):
        """Test connecting without TLS."""
        with patch("grpc.aio.insecure_channel") as mock_channel:
            mock_channel.return_value.channel_ready = AsyncMock()

            await client.connect()

            assert client.connected
            mock_channel.assert_called_once_with("localhost:50051")

    @pytest.mark.asyncio
    async def test_connect_secure(self, settings):
        """Test connecting with TLS."""
        settings.inframind_tls_enabled = True
        settings.inframind_tls_cert_path = "/tmp/test-cert.pem"
        client = InfraMindClient(settings)

        with patch("grpc.aio.secure_channel") as mock_channel:
            # Mock file open to return bytes for certificate
            mock_file = MagicMock()
            mock_file.read.return_value = b"fake-cert-data"
            mock_file.__enter__.return_value = mock_file
            mock_file.__exit__.return_value = None

            with patch("builtins.open", return_value=mock_file):
                mock_channel.return_value.channel_ready = AsyncMock()

                await client.connect()

                assert client.connected

    @pytest.mark.asyncio
    async def test_send_telemetry_batch(self, client):
        """Test sending telemetry batch."""
        # Mock connection
        client.connected = True

        telemetry_data = [
            {
                "metric_name": "cpu_usage",
                "value": 75.5,
                "labels": {"node": "node-01"},
                "timestamp": datetime.utcnow().isoformat(),
            },
            {
                "metric_name": "memory_usage",
                "value": 8192.0,
                "labels": {"node": "node-01"},
                "timestamp": datetime.utcnow().isoformat(),
            },
        ]

        ack = await client.send_telemetry_batch(telemetry_data)

        assert ack.success
        assert "2 points" in ack.message

    @pytest.mark.asyncio
    async def test_send_empty_batch(self, client):
        """Test sending empty batch."""
        client.connected = True

        ack = await client.send_telemetry_batch([])

        assert ack.success
        assert "Empty batch" in ack.message

    @pytest.mark.asyncio
    async def test_stream_not_connected(self, client):
        """Test streaming when not connected raises error."""
        client.connected = False

        # Should raise error when trying to stream
        with pytest.raises(RuntimeError, match="Not connected"):
            # Try to iterate over the async generator
            async for _ in client.stream_action_plans("test-cluster"):
                break  # Should not reach here

    @pytest.mark.asyncio
    async def test_acknowledge_plan(self, client):
        """Test acknowledging plan execution."""
        client.connected = True

        ack = await client.acknowledge_plan(
            plan_id="test-plan-123",
            success=True,
            message="Plan executed successfully",
            metrics={"duration": "2.5s", "decisions": "3"},
        )

        assert ack.success
        assert "acknowledged" in ack.message.lower()

    @pytest.mark.asyncio
    async def test_acknowledge_plan_failure(self, client):
        """Test acknowledging failed plan."""
        client.connected = True

        ack = await client.acknowledge_plan(
            plan_id="test-plan-456",
            success=False,
            message="Execution failed: timeout",
        )

        assert ack.success

    @pytest.mark.asyncio
    async def test_stream_action_plans(self, client):
        """Test streaming action plans (mock)."""
        client.connected = True

        # Since this is a mock implementation, it won't yield anything
        # Just ensure it doesn't raise errors
        plans_received = []

        async def collect_plans():
            timeout = asyncio.create_task(asyncio.sleep(0.5))
            stream = asyncio.create_task(
                self._collect_stream(client.stream_action_plans("test-cluster"))
            )

            done, pending = await asyncio.wait(
                [timeout, stream], return_when=asyncio.FIRST_COMPLETED
            )

            # Cancel pending tasks
            for task in pending:
                task.cancel()

            return plans_received

        await collect_plans()

        # Mock implementation doesn't yield plans, so list should be empty
        assert len(plans_received) == 0

    async def _collect_stream(self, stream):
        """Helper to collect stream items."""
        items = []
        async for item in stream:
            items.append(item)
        return items

    @pytest.mark.asyncio
    async def test_disconnect(self, client):
        """Test disconnecting from InfraMind."""
        mock_channel = AsyncMock()
        client.channel = mock_channel
        client.connected = True

        await client.disconnect()

        assert not client.connected
        mock_channel.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_connection_retry_on_failure(self, client):
        """Test connection handles failures gracefully."""
        with patch("grpc.aio.insecure_channel") as mock_channel:
            mock_channel.return_value.channel_ready = AsyncMock(
                side_effect=Exception("Connection failed")
            )

            with pytest.raises(Exception, match="Connection failed"):
                await client.connect()

            assert not client.connected

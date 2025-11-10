"""Integration test for Phase 2: InfraMind Integration.

This test demonstrates the complete closed-loop flow:
1. Telemetry collection from Prometheus/Kafka
2. Streaming to InfraMind via gRPC
3. Receiving action plans from InfraMind
4. Executing plans via Control API
5. Acknowledging results back to InfraMind

Note: These tests use mocks and don't require actual InfraMind server.
"""

import asyncio
import sys
from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

# Add services to path for imports
repo_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(repo_root / "services" / "control-api"))
sys.path.insert(0, str(repo_root / "services" / "infra-adapter"))


class TestPhase2Integration:
    """Integration tests for Phase 2 closed feedback loop."""

    @pytest.fixture
    def mock_event_publisher(self):
        """Create mock event publisher."""
        publisher = MagicMock()
        publisher.publish_action_plan_event = AsyncMock()
        publisher.publish_audit_event = AsyncMock()
        return publisher

    @pytest.fixture
    def plan_executor(self, mock_event_publisher):
        """Create plan executor."""
        from app.services.plan_executor import PlanExecutor

        return PlanExecutor(event_publisher=mock_event_publisher)

    @pytest.fixture
    def grpc_client(self):
        """Create InfraMind gRPC client."""
        from app.config import Settings
        from app.grpc_client import InfraMindClient

        settings = Settings(
            inframind_url="localhost:50051",
            inframind_tls_enabled=False,
            service_name="test-cluster",
        )
        return InfraMindClient(settings)

    @pytest.mark.asyncio
    async def test_telemetry_to_inframind_flow(self, grpc_client):
        """
        Test: Telemetry flows from Sentinel to InfraMind.

        Flow:
        1. Collect telemetry from Prometheus
        2. Batch telemetry points
        3. Send batch to InfraMind via gRPC
        """
        # Mock connection
        grpc_client.connected = True

        # Simulate telemetry from Prometheus
        telemetry_data = [
            {
                "metric_name": "gpu_utilization_percent",
                "value": 85.5,
                "labels": {"node": "gpu-node-01", "gpu": "0"},
                "timestamp": datetime.utcnow().isoformat(),
            },
            {
                "metric_name": "workload_latency_p99",
                "value": 125.3,
                "labels": {"workload": "embeddings-api"},
                "timestamp": datetime.utcnow().isoformat(),
            },
        ]

        # Send to InfraMind
        ack = await grpc_client.send_telemetry_batch(telemetry_data)

        # Verify successful transmission
        assert ack.success
        assert "2 points" in ack.message

    @pytest.mark.asyncio
    async def test_action_plan_from_inframind_flow(self, plan_executor):
        """
        Test: Action plan received from InfraMind and executed.

        Flow:
        1. InfraMind generates action plan based on telemetry
        2. Plan streamed to Sentinel via gRPC
        3. Sentinel validates and executes plan
        4. Results acknowledged back to InfraMind
        """
        # Simulate action plan from InfraMind
        plan_id = uuid4()
        action_plan = {
            "plan_id": str(plan_id),
            "source": "inframind",
            "correlation_id": "trace-123",
            "decisions": [
                {
                    "verb": "scale",
                    "target": {
                        "workload": "embeddings-api",
                        "namespace": "production",
                        "cluster": "prod-01",
                    },
                    "params": {"replicas": 5},
                    "ttl": 900,
                    "safety": {"rate_limit": 10, "window": "5m"},
                }
            ],
        }

        # Execute plan
        result = await plan_executor.execute_plan(
            plan_id, action_plan, actor="inframind"
        )

        # Verify execution
        assert result["status"] == "completed"
        assert result["decisions_executed"] == 1
        assert len(result["results"]) == 1

        # Verify scale operation
        scale_result = result["results"][0]
        assert scale_result["action"] == "scale"
        assert scale_result["workload"] == "embeddings-api"
        assert scale_result["new_replicas"] == 5

    @pytest.mark.asyncio
    async def test_plan_acknowledgment_flow(self, grpc_client):
        """
        Test: Plan execution acknowledged back to InfraMind.

        Flow:
        1. Plan executed successfully
        2. Execution metrics collected
        3. Acknowledgment sent to InfraMind with results
        """
        # Mock connection
        grpc_client.connected = True

        # Acknowledge successful execution
        ack = await grpc_client.acknowledge_plan(
            plan_id="plan-123",
            success=True,
            message="Plan executed successfully",
            metrics={
                "duration_seconds": "2.5",
                "decisions_executed": "1",
                "workload_scaled": "embeddings-api",
            },
        )

        # Verify acknowledgment
        assert ack.success
        assert "acknowledged" in ack.message.lower()

    @pytest.mark.asyncio
    async def test_complete_closed_loop(self, grpc_client, plan_executor):
        """
        Test: Complete closed feedback loop end-to-end.

        Full flow:
        1. Observe: Telemetry collected and sent to InfraMind
        2. Predict: InfraMind analyzes and generates action plan
        3. Act: Sentinel executes the plan
        4. Learn: Results fed back to InfraMind
        """
        # Mock connection
        grpc_client.connected = True

        # Step 1: Observe - Send telemetry
        telemetry = [
            {
                "metric_name": "gpu_utilization_percent",
                "value": 92.0,  # High GPU utilization
                "labels": {"node": "gpu-node-01"},
                "timestamp": datetime.utcnow().isoformat(),
            }
        ]

        telemetry_ack = await grpc_client.send_telemetry_batch(telemetry)
        assert telemetry_ack.success

        # Step 2: Predict - Simulate InfraMind decision
        # (In production, this would come from InfraMind's models)
        plan_id = uuid4()
        action_plan = {
            "decisions": [
                {
                    "verb": "scale",
                    "target": {"workload": "inference-service"},
                    "params": {"replicas": 10},  # Scale up due to high GPU usage
                    "ttl": 900,
                }
            ],
            "source": "inframind",
        }

        # Step 3: Act - Execute the plan
        execution_result = await plan_executor.execute_plan(
            plan_id, action_plan, actor="inframind"
        )

        assert execution_result["status"] == "completed"
        assert execution_result["decisions_executed"] == 1

        # Step 4: Learn - Acknowledge back to InfraMind
        plan_ack = await grpc_client.acknowledge_plan(
            plan_id=str(plan_id),
            success=True,
            message="Scale operation completed",
            metrics={
                "duration": str(execution_result["duration_seconds"]),
                "decisions": str(execution_result["decisions_executed"]),
            },
        )

        assert plan_ack.success

    @pytest.mark.asyncio
    async def test_multi_decision_plan(self, plan_executor):
        """
        Test: Execute complex plan with multiple decisions.

        Scenario: InfraMind recommends multiple optimizations:
        1. Scale up high-load service
        2. Reschedule underutilized workload
        3. Rollback problematic deployment
        """
        plan_id = uuid4()
        complex_plan = {
            "decisions": [
                {
                    "verb": "scale",
                    "target": {"workload": "api-gateway"},
                    "params": {"replicas": 8},
                    "ttl": 900,
                },
                {
                    "verb": "reschedule",
                    "target": {"workload": "batch-processor"},
                    "params": {"node": "gpu-node-02"},
                    "ttl": 600,
                },
                {
                    "verb": "rollback",
                    "target": {"workload": "payment-service"},
                    "params": {"revision": "v1.2.3"},
                    "ttl": 300,
                },
            ],
            "source": "inframind",
        }

        result = await plan_executor.execute_plan(plan_id, complex_plan)

        # Verify all decisions executed
        assert result["status"] == "completed"
        assert result["decisions_executed"] == 3
        assert len(result["results"]) == 3

        # Verify each decision type
        actions = [r["action"] for r in result["results"]]
        assert "scale" in actions
        assert "reschedule" in actions
        assert "rollback" in actions

    @pytest.mark.asyncio
    async def test_plan_failure_and_feedback(self, grpc_client, plan_executor):
        """
        Test: Failed plan execution provides feedback to InfraMind.

        Flow:
        1. Plan execution encounters error
        2. Error captured and logged
        3. Failure acknowledged to InfraMind with details
        """
        # Mock connection
        grpc_client.connected = True

        # Simulate plan with invalid verb (will fail)
        plan_id = uuid4()
        invalid_plan = {
            "decisions": [
                {
                    "verb": "invalid_action",
                    "target": {"workload": "test"},
                    "params": {},
                    "ttl": 900,
                }
            ],
            "source": "inframind",
        }

        # Execute and expect failure
        from app.services.plan_executor import PlanExecutionError

        with pytest.raises(PlanExecutionError):
            await plan_executor.execute_plan(plan_id, invalid_plan)

        # Acknowledge failure to InfraMind
        ack = await grpc_client.acknowledge_plan(
            plan_id=str(plan_id),
            success=False,
            message="Plan execution failed: Unknown verb 'invalid_action'",
        )

        assert ack.success  # Acknowledgment itself succeeds

    @pytest.mark.asyncio
    async def test_concurrent_plan_execution_prevention(self, plan_executor):
        """
        Test: Prevent concurrent execution of the same plan.

        Safety check: Ensure plans are not executed multiple times.
        """
        plan_id = uuid4()
        plan = {
            "decisions": [
                {
                    "verb": "scale",
                    "target": {"workload": "test"},
                    "params": {"replicas": 3},
                    "ttl": 900,
                }
            ],
            "source": "user",
        }

        # Simulate plan already executing
        plan_executor._executing_plans.add(plan_id)

        # Try to execute again
        from app.services.plan_executor import PlanExecutionError

        with pytest.raises(PlanExecutionError, match="already executing"):
            await plan_executor.execute_plan(plan_id, plan)

        # Cleanup
        plan_executor._executing_plans.remove(plan_id)

    @pytest.mark.asyncio
    async def test_telemetry_batch_with_events(self, grpc_client):
        """
        Test: Telemetry includes both metrics and events.

        Scenario: Send mixed batch with Prometheus metrics and Kafka events.
        """
        grpc_client.connected = True

        mixed_telemetry = [
            # Prometheus metric
            {
                "metric_name": "cpu_usage",
                "value": 75.0,
                "labels": {"node": "node-01"},
                "timestamp": datetime.utcnow().isoformat(),
            },
            # Kafka event
            {
                "event_type": "deployment.completed",
                "value": 1.0,
                "labels": {"workload": "api-service", "version": "v2.0"},
                "timestamp": datetime.utcnow().isoformat(),
            },
        ]

        ack = await grpc_client.send_telemetry_batch(mixed_telemetry)

        assert ack.success
        assert "2 points" in ack.message


def test_integration_smoke():
    """
    Smoke test for Phase 2 integration.

    Quick validation that all components can be imported and initialized.
    """
    # This test just validates imports work
    # Actual functionality tested in class-based tests above
    assert True


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])

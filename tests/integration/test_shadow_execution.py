"""Integration tests for shadow mode execution."""

import pytest
from uuid import uuid4

from app.services.plan_executor import PlanExecutor


@pytest.mark.integration
@pytest.mark.asyncio
class TestShadowExecution:
    """Integration tests for shadow mode plan execution."""

    async def test_shadow_mode_scale_operation(self):
        """Test shadow mode for scale operations."""
        executor = PlanExecutor()

        plan_id = uuid4()
        plan_data = {
            "id": plan_id,
            "decisions": [
                {
                    "verb": "scale",
                    "target": {"workload": "test-app", "namespace": "default"},
                    "params": {"replicas": 10},
                    "ttl": 900,
                }
            ],
            "source": "user",
        }

        # Execute in shadow mode
        result = await executor.execute_plan(
            plan_id, plan_data, actor="test-user", shadow_mode=True
        )

        # Verify shadow execution
        assert result["status"] == "completed"
        assert len(result["results"]) == 1

        decision_result = result["results"][0]
        assert decision_result["status"] == "simulated"
        assert decision_result["shadow_mode"] is True
        assert decision_result["would_execute"] is True
        assert decision_result["action"] == "scale"

    async def test_shadow_mode_multiple_decisions(self):
        """Test shadow mode with multiple decisions."""
        executor = PlanExecutor()

        plan_id = uuid4()
        plan_data = {
            "id": plan_id,
            "decisions": [
                {
                    "verb": "scale",
                    "target": {"workload": "app-1"},
                    "params": {"replicas": 5},
                    "ttl": 900,
                },
                {
                    "verb": "update",
                    "target": {"workload": "app-2"},
                    "params": {"image": "app:v2.0"},
                    "ttl": 900,
                },
                {
                    "verb": "rollback",
                    "target": {"workload": "app-3"},
                    "params": {"revision": "previous"},
                    "ttl": 900,
                },
            ],
            "source": "InfraMind",
        }

        result = await executor.execute_plan(
            plan_id, plan_data, actor="system", shadow_mode=True
        )

        assert result["status"] == "completed"
        assert len(result["results"]) == 3

        # Verify all decisions were simulated
        for decision_result in result["results"]:
            assert decision_result["status"] == "simulated"
            assert decision_result["shadow_mode"] is True
            assert decision_result["would_execute"] is True

    async def test_shadow_mode_vs_live_execution(self):
        """Compare shadow mode vs live execution behavior."""
        executor = PlanExecutor()

        plan_id_shadow = uuid4()
        plan_id_live = uuid4()

        plan_data = {
            "id": plan_id_shadow,
            "decisions": [
                {
                    "verb": "scale",
                    "target": {"workload": "test-app"},
                    "params": {"replicas": 3},
                    "ttl": 900,
                }
            ],
            "source": "user",
        }

        # Execute in shadow mode
        shadow_result = await executor.execute_plan(
            plan_id_shadow, plan_data, actor="test-user", shadow_mode=True
        )

        # Execute in live mode
        plan_data["id"] = plan_id_live
        live_result = await executor.execute_plan(
            plan_id_live, plan_data, actor="test-user", shadow_mode=False
        )

        # Both should complete
        assert shadow_result["status"] == "completed"
        assert live_result["status"] == "completed"

        # Shadow should have simulated status
        assert shadow_result["results"][0]["status"] == "simulated"

        # Live should have mocked/success status
        assert "mocked" in live_result["results"][0]["status"]

        # Shadow execution should be faster (no actual operations)
        assert shadow_result["duration_seconds"] < live_result["duration_seconds"]

    async def test_shadow_mode_reschedule_operation(self):
        """Test shadow mode for reschedule operations."""
        executor = PlanExecutor()

        plan_id = uuid4()
        plan_data = {
            "id": plan_id,
            "decisions": [
                {
                    "verb": "reschedule",
                    "target": {"workload": "test-app"},
                    "params": {"node": "node-gpu-1"},
                    "ttl": 900,
                }
            ],
            "source": "InfraMind",
        }

        result = await executor.execute_plan(
            plan_id, plan_data, actor="system", shadow_mode=True
        )

        assert result["status"] == "completed"
        decision_result = result["results"][0]
        assert decision_result["action"] == "reschedule"
        assert decision_result["status"] == "simulated"
        assert decision_result["target_node"] == "node-gpu-1"

    async def test_shadow_mode_rollback_operation(self):
        """Test shadow mode for rollback operations."""
        executor = PlanExecutor()

        plan_id = uuid4()
        plan_data = {
            "id": plan_id,
            "decisions": [
                {
                    "verb": "rollback",
                    "target": {"workload": "test-app"},
                    "params": {"revision": "v1.2.3"},
                    "ttl": 900,
                }
            ],
            "source": "user",
        }

        result = await executor.execute_plan(
            plan_id, plan_data, actor="operator", shadow_mode=True
        )

        assert result["status"] == "completed"
        decision_result = result["results"][0]
        assert decision_result["action"] == "rollback"
        assert decision_result["status"] == "simulated"
        assert decision_result["revision"] == "v1.2.3"

    async def test_shadow_mode_update_operation(self):
        """Test shadow mode for update operations."""
        executor = PlanExecutor()

        plan_id = uuid4()
        plan_data = {
            "id": plan_id,
            "decisions": [
                {
                    "verb": "update",
                    "target": {"workload": "test-app"},
                    "params": {"image": "myapp:v2.0", "replicas": 5},
                    "ttl": 900,
                }
            ],
            "source": "user",
        }

        result = await executor.execute_plan(
            plan_id, plan_data, actor="developer", shadow_mode=True
        )

        assert result["status"] == "completed"
        decision_result = result["results"][0]
        assert decision_result["action"] == "update"
        assert decision_result["status"] == "simulated"
        assert decision_result["params"]["image"] == "myapp:v2.0"

    async def test_shadow_mode_validation_still_applies(self):
        """Test that policy validation still applies in shadow mode."""
        from sentinel_policy import PolicyEngine, EvaluationMode

        # Create executor with policy engine
        policy_engine = PolicyEngine(mode=EvaluationMode.ENFORCE)
        executor = PlanExecutor(policy_engine=policy_engine)

        plan_id = uuid4()
        plan_data = {
            "id": plan_id,
            "decisions": [
                {
                    "verb": "scale",
                    "target": {"workload": "test-app"},
                    "params": {"replicas": 5},
                    "ttl": 900,
                }
            ],
            "source": "user",
        }

        # Shadow mode should still go through validation
        result = await executor.execute_plan(
            plan_id, plan_data, actor="test-user", shadow_mode=True
        )

        # Execution should complete (validation passed)
        assert result["status"] == "completed"
        assert result["results"][0]["status"] == "simulated"

    async def test_shadow_mode_performance(self):
        """Test that shadow mode is faster than live execution."""
        executor = PlanExecutor()

        # Create plan with multiple decisions
        plan_data = {
            "id": uuid4(),
            "decisions": [
                {
                    "verb": "scale",
                    "target": {"workload": f"app-{i}"},
                    "params": {"replicas": 3},
                    "ttl": 900,
                }
                for i in range(5)
            ],
            "source": "user",
        }

        # Shadow execution
        shadow_result = await executor.execute_plan(
            uuid4(), plan_data, shadow_mode=True
        )

        # Live execution
        live_result = await executor.execute_plan(
            uuid4(), plan_data, shadow_mode=False
        )

        # Shadow should be significantly faster
        assert shadow_result["duration_seconds"] < live_result["duration_seconds"] * 0.5

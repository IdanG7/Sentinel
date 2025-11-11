"""Tests for Plan Executor."""

import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

from app.services.plan_executor import PlanExecutor, PlanExecutionError


class TestPlanExecutor:
    """Test cases for Plan Executor."""

    @pytest.fixture
    def mock_event_publisher(self):
        """Create mock event publisher."""
        publisher = MagicMock()
        publisher.publish_action_plan_event = AsyncMock()
        publisher.publish_audit_event = AsyncMock()
        return publisher

    @pytest.fixture
    def mock_k8s_driver(self):
        """Create mock K8s driver."""
        driver = MagicMock()
        driver.scale_deployment = AsyncMock(
            return_value={"previous_replicas": 3, "new_replicas": 5}
        )
        return driver

    @pytest.fixture
    def executor(self, mock_event_publisher, mock_k8s_driver):
        """Create plan executor."""
        return PlanExecutor(event_publisher=mock_event_publisher, k8s_driver=mock_k8s_driver)

    @pytest.mark.asyncio
    async def test_execute_simple_scale_plan(self, executor):
        """Test executing a simple scale plan."""
        plan_id = uuid4()
        plan_data = {
            "decisions": [
                {
                    "verb": "scale",
                    "target": {"workload": "test-deployment", "namespace": "default"},
                    "params": {"replicas": 5},
                    "ttl": 900,
                }
            ],
            "source": "inframind",
        }

        result = await executor.execute_plan(plan_id, plan_data, actor="admin")

        assert result["status"] == "completed"
        assert result["decisions_executed"] == 1
        assert plan_id not in executor._executing_plans
        assert plan_id in executor._execution_history

    @pytest.mark.asyncio
    async def test_execute_multiple_decisions(self, executor):
        """Test executing plan with multiple decisions."""
        plan_id = uuid4()
        plan_data = {
            "decisions": [
                {
                    "verb": "scale",
                    "target": {"workload": "app-1"},
                    "params": {"replicas": 3},
                    "ttl": 900,
                },
                {
                    "verb": "scale",
                    "target": {"workload": "app-2"},
                    "params": {"replicas": 2},
                    "ttl": 900,
                },
            ],
            "source": "user",
        }

        result = await executor.execute_plan(plan_id, plan_data)

        assert result["status"] == "completed"
        assert result["decisions_executed"] == 2
        assert len(result["results"]) == 2

    @pytest.mark.asyncio
    async def test_execute_plan_already_executing(self, executor):
        """Test executing plan that's already running."""
        plan_id = uuid4()
        plan_data = {"decisions": [], "source": "user"}

        # Add to executing set
        executor._executing_plans.add(plan_id)

        with pytest.raises(PlanExecutionError, match="already executing"):
            await executor.execute_plan(plan_id, plan_data)

    @pytest.mark.asyncio
    async def test_execute_plan_with_failure(self, executor, mock_k8s_driver):
        """Test plan execution with decision failure."""
        # Make K8s driver fail
        mock_k8s_driver.scale_deployment = AsyncMock(side_effect=Exception("Scale failed"))

        plan_id = uuid4()
        plan_data = {
            "decisions": [
                {
                    "verb": "scale",
                    "target": {"workload": "test-deployment"},
                    "params": {"replicas": 5},
                    "ttl": 900,
                }
            ],
            "source": "inframind",
        }

        with pytest.raises(PlanExecutionError):
            await executor.execute_plan(plan_id, plan_data)

        # Check execution history records failure
        history = executor._execution_history.get(plan_id)
        assert history is not None
        assert history["status"] == "failed"

    @pytest.mark.asyncio
    async def test_handle_unknown_verb(self, executor):
        """Test handling unknown action verb."""
        plan_id = uuid4()
        plan_data = {
            "decisions": [
                {
                    "verb": "unknown_action",
                    "target": {"workload": "test"},
                    "params": {},
                    "ttl": 900,
                }
            ],
            "source": "user",
        }

        with pytest.raises(PlanExecutionError, match="Unknown verb"):
            await executor.execute_plan(plan_id, plan_data)

    @pytest.mark.asyncio
    async def test_handle_reschedule(self, executor):
        """Test handling reschedule decision."""
        plan_id = uuid4()
        plan_data = {
            "decisions": [
                {
                    "verb": "reschedule",
                    "target": {"workload": "test-app"},
                    "params": {"node": "node-02"},
                    "ttl": 900,
                }
            ],
            "source": "inframind",
        }

        result = await executor.execute_plan(plan_id, plan_data)

        assert result["status"] == "completed"
        assert result["results"][0]["action"] == "reschedule"

    @pytest.mark.asyncio
    async def test_handle_rollback(self, executor):
        """Test handling rollback decision."""
        plan_id = uuid4()
        plan_data = {
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

        result = await executor.execute_plan(plan_id, plan_data)

        assert result["status"] == "completed"
        assert result["results"][0]["action"] == "rollback"
        assert result["results"][0]["revision"] == "v1.2.3"

    @pytest.mark.asyncio
    async def test_handle_update(self, executor):
        """Test handling update decision."""
        plan_id = uuid4()
        plan_data = {
            "decisions": [
                {
                    "verb": "update",
                    "target": {"workload": "test-app"},
                    "params": {"image": "app:v2.0"},
                    "ttl": 900,
                }
            ],
            "source": "inframind",
        }

        result = await executor.execute_plan(plan_id, plan_data)

        assert result["status"] == "completed"
        assert result["results"][0]["action"] == "update"

    @pytest.mark.asyncio
    async def test_get_execution_status_in_progress(self, executor):
        """Test getting status of executing plan."""
        plan_id = uuid4()

        # Simulate plan in execution
        executor._executing_plans.add(plan_id)

        status = executor.get_execution_status(plan_id)

        assert status is not None
        assert status["status"] == "executing"
        assert status["plan_id"] == str(plan_id)

        executor._executing_plans.remove(plan_id)

    @pytest.mark.asyncio
    async def test_get_execution_status_completed(self, executor):
        """Test getting status of completed plan."""
        plan_id = uuid4()
        plan_data = {
            "decisions": [
                {
                    "verb": "scale",
                    "target": {"workload": "test"},
                    "params": {"replicas": 2},
                    "ttl": 900,
                }
            ],
            "source": "user",
        }

        # Execute plan
        await executor.execute_plan(plan_id, plan_data)

        status = executor.get_execution_status(plan_id)

        assert status is not None
        assert status["status"] == "completed"
        assert "duration_seconds" in status

    @pytest.mark.asyncio
    async def test_get_execution_status_not_found(self, executor):
        """Test getting status of non-existent plan."""
        plan_id = uuid4()

        status = executor.get_execution_status(plan_id)

        assert status is None

    @pytest.mark.asyncio
    async def test_validation_without_policy_engine(self, executor):
        """Test validation skips when policy engine is None."""
        plan_data = {"decisions": []}

        result = await executor._validate_plan(plan_data)

        assert result["valid"]
        assert "No policy engine" in result["reason"]

    @pytest.mark.asyncio
    async def test_event_publishing(self, executor, mock_event_publisher):
        """Test events are published during execution."""
        plan_id = uuid4()
        plan_data = {
            "decisions": [
                {
                    "verb": "scale",
                    "target": {"workload": "test"},
                    "params": {"replicas": 3},
                    "ttl": 900,
                }
            ],
            "source": "inframind",
        }

        await executor.execute_plan(plan_id, plan_data, actor="admin")

        # Verify events were published
        assert mock_event_publisher.publish_action_plan_event.called
        assert mock_event_publisher.publish_audit_event.called

        # Check for completion event
        calls = mock_event_publisher.publish_action_plan_event.call_args_list
        event_types = [call[1]["event_type"] for call in calls]
        assert "action_plan.completed" in event_types

    @pytest.mark.asyncio
    async def test_execution_metrics(self, executor):
        """Test execution metrics are recorded."""
        plan_id = uuid4()
        plan_data = {
            "decisions": [
                {
                    "verb": "scale",
                    "target": {"workload": "test"},
                    "params": {"replicas": 5},
                    "ttl": 900,
                }
            ],
            "source": "user",
        }

        result = await executor.execute_plan(plan_id, plan_data)

        assert "duration_seconds" in result
        assert result["duration_seconds"] >= 0
        assert "executed_at" in result
        assert isinstance(result["executed_at"], datetime)

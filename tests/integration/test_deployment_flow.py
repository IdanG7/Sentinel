"""Integration test for full deployment flow."""

import pytest
from uuid import uuid4
from datetime import datetime

from sentinel_k8s import DeploymentSpec
from sentinel_policy import (
    ActionPlan,
    ActionPlanSource,
    Decision,
    DecisionVerb,
    Policy,
    PolicyEngine,
    PolicyRule,
    PolicyRuleType,
    EvaluationMode,
)


@pytest.mark.integration
class TestDeploymentFlow:
    """Integration tests for deployment flow."""

    def test_policy_validation_flow(self):
        """Test full policy validation flow."""
        # 1. Create policy engine with quota policy
        engine = PolicyEngine(mode=EvaluationMode.ENFORCE)

        policy = Policy(
            id=uuid4(),
            name="Production Quota",
            rules=[
                PolicyRule(
                    type=PolicyRuleType.QUOTA,
                    constraint={"max_replicas": 10, "max_gpus": 4},
                    action_on_violation="reject",
                ),
            ],
            priority=100,
            enabled=True,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )

        engine.register_policy(policy)

        # 2. Create action plan within limits - should pass
        valid_plan = ActionPlan(
            id=uuid4(),
            decisions=[
                Decision(
                    verb=DecisionVerb.SCALE,
                    target={"deployment_id": str(uuid4())},
                    params={"replicas": 5, "total_gpus": 2},
                    ttl=900,
                ),
            ],
            source=ActionPlanSource.USER,
            created_at=datetime.utcnow(),
        )

        result = engine.evaluate(valid_plan)
        assert result.approved is True
        assert len(result.violations) == 0

        # 3. Create action plan exceeding limits - should fail
        invalid_plan = ActionPlan(
            id=uuid4(),
            decisions=[
                Decision(
                    verb=DecisionVerb.SCALE,
                    target={"deployment_id": str(uuid4())},
                    params={"replicas": 20, "total_gpus": 8},
                    ttl=900,
                ),
            ],
            source=ActionPlanSource.USER,
            created_at=datetime.utcnow(),
        )

        result = engine.evaluate(invalid_plan)
        assert result.approved is False
        assert len(result.violations) > 0

    def test_dry_run_mode(self):
        """Test dry-run mode allows violations."""
        # Create engine in dry-run mode
        engine = PolicyEngine(mode=EvaluationMode.DRY_RUN)

        policy = Policy(
            id=uuid4(),
            name="Cost Policy",
            rules=[
                PolicyRule(
                    type=PolicyRuleType.COST_CEILING,
                    constraint={"max_cost_per_hour": 50},
                    action_on_violation="reject",
                ),
            ],
            priority=100,
            enabled=True,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )

        engine.register_policy(policy)

        # Create action plan that violates cost ceiling
        plan = ActionPlan(
            id=uuid4(),
            decisions=[
                Decision(
                    verb=DecisionVerb.SCALE,
                    target={"deployment_id": str(uuid4())},
                    params={"replicas": 10, "estimated_cost_per_hour": 100},
                    ttl=900,
                ),
            ],
            source=ActionPlanSource.INFRAMIND,
            created_at=datetime.utcnow(),
        )

        result = engine.evaluate(plan)

        # Should approve in dry-run mode but log violations
        assert result.approved is True
        assert len(result.violations) > 0
        assert result.mode == EvaluationMode.DRY_RUN

    def test_multi_policy_evaluation(self):
        """Test evaluation with multiple policies."""
        engine = PolicyEngine()

        # Add multiple policies with different priorities
        cost_policy = Policy(
            id=uuid4(),
            name="Cost Policy",
            rules=[
                PolicyRule(
                    type=PolicyRuleType.COST_CEILING,
                    constraint={"max_cost_per_hour": 100},
                    action_on_violation="reject",
                ),
            ],
            priority=200,  # Higher priority
            enabled=True,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )

        quota_policy = Policy(
            id=uuid4(),
            name="Quota Policy",
            rules=[
                PolicyRule(
                    type=PolicyRuleType.QUOTA,
                    constraint={"max_replicas": 5},
                    action_on_violation="reject",
                ),
            ],
            priority=100,  # Lower priority
            enabled=True,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )

        engine.register_policy(cost_policy)
        engine.register_policy(quota_policy)

        # Create action plan that violates both policies
        plan = ActionPlan(
            id=uuid4(),
            decisions=[
                Decision(
                    verb=DecisionVerb.SCALE,
                    target={"deployment_id": str(uuid4())},
                    params={
                        "replicas": 10,  # Violates quota
                        "estimated_cost_per_hour": 150,  # Violates cost
                    },
                    ttl=900,
                ),
            ],
            source=ActionPlanSource.USER,
            created_at=datetime.utcnow(),
        )

        result = engine.evaluate(plan)

        # Should have violations from both policies
        assert result.approved is False
        assert len(result.violations) == 2

        violation_types = {v.rule_type for v in result.violations}
        assert PolicyRuleType.COST_CEILING in violation_types
        assert PolicyRuleType.QUOTA in violation_types

    @pytest.mark.asyncio
    async def test_database_workflow(self, test_db):
        """Test database operations workflow."""
        from services.control_api.app.crud import workload as workload_crud
        from services.control_api.app.models.schemas import WorkloadCreate

        # Create a workload
        workload_data = WorkloadCreate(
            name="test-workload",
            type="inference",
            image="nginx:latest",
            resources={"cpu": "2", "memory": "4Gi"},
        )

        workload = await workload_crud.create(test_db, obj_in=workload_data)

        assert workload.id is not None
        assert workload.name == "test-workload"
        assert workload.type == "inference"

        # Retrieve the workload
        retrieved = await workload_crud.get(test_db, workload.id)
        assert retrieved is not None
        assert retrieved.id == workload.id

        # List workloads
        workloads = await workload_crud.get_multi(test_db)
        assert len(workloads) == 1

        # Delete workload
        deleted = await workload_crud.delete(test_db, id=workload.id)
        assert deleted is not None

        # Verify deletion
        retrieved_after_delete = await workload_crud.get(test_db, workload.id)
        assert retrieved_after_delete is None

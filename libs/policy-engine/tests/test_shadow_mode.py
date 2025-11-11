"""Tests for shadow evaluation mode."""

import pytest
from datetime import datetime
from uuid import uuid4

from sentinel_policy import (
    ActionPlan,
    Decision,
    DecisionVerb,
    ActionPlanSource,
    Policy,
    PolicyRule,
    PolicyRuleType,
    PolicyEngine,
    EvaluationMode,
)


class TestShadowMode:
    """Test shadow evaluation mode functionality."""

    def test_shadow_mode_allows_violations(self):
        """Test that shadow mode approves plans even with violations."""
        engine = PolicyEngine(mode=EvaluationMode.SHADOW)

        # Create policy that would normally block
        policy = Policy(
            id=uuid4(),
            name="Strict Quota",
            rules=[
                PolicyRule(
                    type=PolicyRuleType.QUOTA,
                    constraint={"max_replicas": 5},
                    action_on_violation="reject",
                ),
            ],
            priority=100,
            enabled=True,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )

        engine.register_policy(policy)

        # Create plan that violates quota
        plan = ActionPlan(
            id=uuid4(),
            decisions=[
                Decision(
                    verb=DecisionVerb.SCALE,
                    target={"deployment_id": str(uuid4())},
                    params={"replicas": 10},  # Exceeds max_replicas
                    ttl=900,
                ),
            ],
            source=ActionPlanSource.INFRAMIND,
            created_at=datetime.utcnow(),
        )

        result = engine.evaluate(plan)

        # Should be approved in shadow mode despite violation
        assert result.approved is True
        assert len(result.violations) == 1  # Violation still recorded
        assert result.mode == EvaluationMode.SHADOW
        assert result.violations[0].rule_type == PolicyRuleType.QUOTA

    def test_shadow_mode_logs_all_violations(self):
        """Test that shadow mode logs all violations without rejecting."""
        engine = PolicyEngine(mode=EvaluationMode.SHADOW)

        # Add multiple policies that would be violated
        cost_policy = Policy(
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

        quota_policy = Policy(
            id=uuid4(),
            name="Quota Policy",
            rules=[
                PolicyRule(
                    type=PolicyRuleType.QUOTA,
                    constraint={"max_replicas": 3},
                    action_on_violation="reject",
                ),
            ],
            priority=90,
            enabled=True,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )

        engine.register_policy(cost_policy)
        engine.register_policy(quota_policy)

        # Create plan that violates both policies
        plan = ActionPlan(
            id=uuid4(),
            decisions=[
                Decision(
                    verb=DecisionVerb.SCALE,
                    target={"deployment_id": str(uuid4())},
                    params={
                        "replicas": 10,  # Violates quota
                        "estimated_cost_per_hour": 100,  # Violates cost
                    },
                    ttl=900,
                ),
            ],
            source=ActionPlanSource.INFRAMIND,
            created_at=datetime.utcnow(),
        )

        result = engine.evaluate(plan)

        # Should be approved with both violations logged
        assert result.approved is True
        assert len(result.violations) == 2
        assert result.mode == EvaluationMode.SHADOW

        # Verify both violation types are recorded
        violation_types = {v.rule_type for v in result.violations}
        assert PolicyRuleType.COST_CEILING in violation_types
        assert PolicyRuleType.QUOTA in violation_types

    def test_shadow_mode_with_no_violations(self):
        """Test shadow mode with a valid plan (no violations)."""
        engine = PolicyEngine(mode=EvaluationMode.SHADOW)

        policy = Policy(
            id=uuid4(),
            name="Quota Policy",
            rules=[
                PolicyRule(
                    type=PolicyRuleType.QUOTA,
                    constraint={"max_replicas": 20},
                    action_on_violation="reject",
                ),
            ],
            priority=100,
            enabled=True,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )

        engine.register_policy(policy)

        # Create valid plan
        plan = ActionPlan(
            id=uuid4(),
            decisions=[
                Decision(
                    verb=DecisionVerb.SCALE,
                    target={"deployment_id": str(uuid4())},
                    params={"replicas": 5},  # Within limits
                    ttl=900,
                ),
            ],
            source=ActionPlanSource.USER,
            created_at=datetime.utcnow(),
        )

        result = engine.evaluate(plan)

        # Should be approved with no violations
        assert result.approved is True
        assert len(result.violations) == 0
        assert result.mode == EvaluationMode.SHADOW

    def test_shadow_vs_enforce_mode(self):
        """Compare shadow mode behavior with enforce mode."""
        # Test in enforce mode first
        enforce_engine = PolicyEngine(mode=EvaluationMode.ENFORCE)

        policy = Policy(
            id=uuid4(),
            name="Test Policy",
            rules=[
                PolicyRule(
                    type=PolicyRuleType.QUOTA,
                    constraint={"max_replicas": 5},
                    action_on_violation="reject",
                ),
            ],
            priority=100,
            enabled=True,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )

        enforce_engine.register_policy(policy)

        plan = ActionPlan(
            id=uuid4(),
            decisions=[
                Decision(
                    verb=DecisionVerb.SCALE,
                    target={"deployment_id": str(uuid4())},
                    params={"replicas": 10},
                    ttl=900,
                ),
            ],
            source=ActionPlanSource.INFRAMIND,
            created_at=datetime.utcnow(),
        )

        enforce_result = enforce_engine.evaluate(plan)

        # Enforce mode should reject
        assert enforce_result.approved is False
        assert len(enforce_result.violations) == 1

        # Now test in shadow mode
        shadow_engine = PolicyEngine(mode=EvaluationMode.SHADOW)
        shadow_engine.register_policy(policy)

        shadow_result = shadow_engine.evaluate(plan)

        # Shadow mode should approve
        assert shadow_result.approved is True
        assert len(shadow_result.violations) == 1  # Same violation count
        assert shadow_result.mode == EvaluationMode.SHADOW

    def test_shadow_mode_timing(self):
        """Test that shadow mode evaluation completes quickly."""
        engine = PolicyEngine(mode=EvaluationMode.SHADOW)

        policy = Policy(
            id=uuid4(),
            name="Test Policy",
            rules=[
                PolicyRule(
                    type=PolicyRuleType.QUOTA,
                    constraint={"max_replicas": 5},
                    action_on_violation="reject",
                ),
            ],
            priority=100,
            enabled=True,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )

        engine.register_policy(policy)

        plan = ActionPlan(
            id=uuid4(),
            decisions=[
                Decision(
                    verb=DecisionVerb.SCALE,
                    target={"deployment_id": str(uuid4())},
                    params={"replicas": 10},
                    ttl=900,
                ),
            ],
            source=ActionPlanSource.INFRAMIND,
            created_at=datetime.utcnow(),
        )

        result = engine.evaluate(plan)

        # Should complete quickly (< 100ms typical)
        assert result.duration_ms < 1000  # Generous upper bound
        assert result.approved is True

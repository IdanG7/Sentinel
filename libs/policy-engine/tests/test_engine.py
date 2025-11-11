"""Tests for Policy Engine."""

import pytest
from datetime import datetime
from uuid import uuid4

from sentinel_policy import (
    ActionPlan,
    ActionPlanSource,
    Decision,
    DecisionVerb,
    EvaluationMode,
    Policy,
    PolicyEngine,
    PolicyRule,
    PolicyRuleType,
)


class TestPolicyEngine:
    """Test cases for PolicyEngine."""

    def test_init(self):
        """Test PolicyEngine initialization."""
        engine = PolicyEngine(mode=EvaluationMode.ENFORCE)
        assert engine.mode == EvaluationMode.ENFORCE
        assert len(engine._policies) == 0

    def test_register_policy(self, sample_policy):
        """Test registering a policy."""
        engine = PolicyEngine()
        engine.register_policy(sample_policy)

        assert str(sample_policy.id) in engine._policies
        assert engine._policies[str(sample_policy.id)] == sample_policy

    def test_unregister_policy(self, sample_policy):
        """Test unregistering a policy."""
        engine = PolicyEngine()
        engine.register_policy(sample_policy)

        result = engine.unregister_policy(str(sample_policy.id))
        assert result is True
        assert str(sample_policy.id) not in engine._policies

        # Try unregistering non-existent policy
        result = engine.unregister_policy(str(uuid4()))
        assert result is False

    def test_list_policies(self, sample_policy, sample_sla_policy):
        """Test listing policies."""
        engine = PolicyEngine()
        engine.register_policy(sample_policy)
        engine.register_policy(sample_sla_policy)

        policies = engine.list_policies()
        assert len(policies) == 2
        # Should be sorted by priority (highest first)
        assert policies[0].priority >= policies[1].priority

    def test_list_enabled_policies_only(self, sample_policy):
        """Test listing only enabled policies."""
        engine = PolicyEngine()

        # Add enabled policy
        engine.register_policy(sample_policy)

        # Add disabled policy
        disabled_policy = Policy(
            id=uuid4(),
            name="Disabled Policy",
            rules=[
                PolicyRule(
                    type=PolicyRuleType.QUOTA,
                    constraint={},
                    action_on_violation="reject",
                )
            ],
            priority=50,
            enabled=False,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        engine.register_policy(disabled_policy)

        policies = engine.list_policies(enabled_only=True)
        assert len(policies) == 1
        assert policies[0].enabled is True

    def test_evaluate_approve(self, sample_policy, sample_action_plan):
        """Test evaluating an action plan that should be approved."""
        engine = PolicyEngine(mode=EvaluationMode.ENFORCE)
        engine.register_policy(sample_policy)

        result = engine.evaluate(sample_action_plan)

        assert result.approved is True
        assert len(result.violations) == 0
        assert result.mode == EvaluationMode.ENFORCE

    def test_evaluate_reject_cost_ceiling(self, sample_policy, violating_action_plan):
        """Test rejecting an action plan that violates cost ceiling."""
        engine = PolicyEngine(mode=EvaluationMode.ENFORCE)
        engine.register_policy(sample_policy)

        result = engine.evaluate(violating_action_plan)

        assert result.approved is False
        assert len(result.violations) == 1
        assert result.violations[0].rule_type == PolicyRuleType.COST_CEILING
        assert "Cost ceiling exceeded" in result.violations[0].message

    def test_evaluate_reject_quota(self, sample_policy, quota_violating_action_plan):
        """Test rejecting an action plan that violates quota."""
        engine = PolicyEngine(mode=EvaluationMode.ENFORCE)
        engine.register_policy(sample_policy)

        result = engine.evaluate(quota_violating_action_plan)

        assert result.approved is False
        assert len(result.violations) >= 1
        # Should have violations for both replica and GPU quotas
        violation_types = [v.rule_type for v in result.violations]
        assert PolicyRuleType.QUOTA in violation_types

    def test_evaluate_dry_run_mode(self, sample_policy, violating_action_plan):
        """Test dry-run mode allows violations but logs them."""
        engine = PolicyEngine(mode=EvaluationMode.DRY_RUN)
        engine.register_policy(sample_policy)

        result = engine.evaluate(violating_action_plan)

        # In dry-run mode, should still be approved despite violations
        assert result.approved is True
        assert len(result.violations) > 0
        assert result.mode == EvaluationMode.DRY_RUN

    def test_cost_ceiling_enforcement(self):
        """Test cost ceiling rule enforcement."""
        engine = PolicyEngine()
        policy = Policy(
            id=uuid4(),
            name="Cost Policy",
            rules=[
                PolicyRule(
                    type=PolicyRuleType.COST_CEILING,
                    constraint={"max_cost_per_hour": 50, "currency": "USD"},
                    action_on_violation="reject",
                ),
            ],
            priority=100,
            enabled=True,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        engine.register_policy(policy)

        # Under budget - should pass
        good_plan = ActionPlan(
            id=uuid4(),
            decisions=[
                Decision(
                    verb=DecisionVerb.SCALE,
                    target={"deployment_id": str(uuid4())},
                    params={"replicas": 2, "estimated_cost_per_hour": 30},
                    ttl=900,
                ),
            ],
            source=ActionPlanSource.USER,
            created_at=datetime.utcnow(),
        )

        result = engine.evaluate(good_plan)
        assert result.approved is True

        # Over budget - should fail
        bad_plan = ActionPlan(
            id=uuid4(),
            decisions=[
                Decision(
                    verb=DecisionVerb.SCALE,
                    target={"deployment_id": str(uuid4())},
                    params={"replicas": 10, "estimated_cost_per_hour": 100},
                    ttl=900,
                ),
            ],
            source=ActionPlanSource.USER,
            created_at=datetime.utcnow(),
        )

        result = engine.evaluate(bad_plan)
        assert result.approved is False

    def test_quota_enforcement(self):
        """Test quota rule enforcement."""
        engine = PolicyEngine()
        policy = Policy(
            id=uuid4(),
            name="Quota Policy",
            rules=[
                PolicyRule(
                    type=PolicyRuleType.QUOTA,
                    constraint={
                        "max_replicas": 5,
                        "max_cpu_cores": 20,
                        "max_memory_gi": 40,
                        "max_gpus": 2,
                    },
                    action_on_violation="reject",
                ),
            ],
            priority=100,
            enabled=True,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        engine.register_policy(policy)

        # Test replica quota violation
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
            source=ActionPlanSource.USER,
            created_at=datetime.utcnow(),
        )

        result = engine.evaluate(plan)
        assert result.approved is False
        assert any("Replica quota exceeded" in v.message for v in result.violations)

    def test_slo_enforcement(self):
        """Test SLO rule enforcement."""
        engine = PolicyEngine()
        policy = Policy(
            id=uuid4(),
            name="SLO Policy",
            rules=[
                PolicyRule(
                    type=PolicyRuleType.SLO,
                    constraint={
                        "max_p99_latency_ms": 500,
                        "min_success_rate_percent": 99.5,
                    },
                    action_on_violation="reject",
                ),
            ],
            priority=100,
            enabled=True,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        engine.register_policy(policy)

        # Test latency SLO violation
        plan = ActionPlan(
            id=uuid4(),
            decisions=[
                Decision(
                    verb=DecisionVerb.SCALE,
                    target={"deployment_id": str(uuid4())},
                    params={
                        "replicas": 1,
                        "current_p99_latency_ms": 600,
                    },  # Exceeds SLO
                    ttl=900,
                ),
            ],
            source=ActionPlanSource.USER,
            created_at=datetime.utcnow(),
        )

        result = engine.evaluate(plan)
        assert result.approved is False
        assert any("Latency SLO violation" in v.message for v in result.violations)

    def test_sla_enforcement(self, sample_sla_policy):
        """Test SLA rule enforcement."""
        engine = PolicyEngine()
        engine.register_policy(sample_sla_policy)

        # Test SLA violation
        plan = ActionPlan(
            id=uuid4(),
            decisions=[
                Decision(
                    verb=DecisionVerb.SCALE,
                    target={"deployment_id": str(uuid4())},
                    params={"replicas": 1, "current_uptime_percent": 99.0},  # Below SLA
                    ttl=900,
                ),
            ],
            source=ActionPlanSource.USER,
            created_at=datetime.utcnow(),
        )

        result = engine.evaluate(plan)
        assert result.approved is False
        assert any("SLA violation risk" in v.message for v in result.violations)

    def test_selector_matching(self):
        """Test policy selector matching."""
        engine = PolicyEngine()

        # Policy with selector for production only
        policy = Policy(
            id=uuid4(),
            name="Production Policy",
            rules=[
                PolicyRule(
                    type=PolicyRuleType.COST_CEILING,
                    constraint={"max_cost_per_hour": 10},
                    action_on_violation="reject",
                ),
            ],
            priority=100,
            enabled=True,
            selector={"environment": "production"},
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        engine.register_policy(policy)

        # Plan targeting production - should be evaluated
        prod_plan = ActionPlan(
            id=uuid4(),
            decisions=[
                Decision(
                    verb=DecisionVerb.SCALE,
                    target={"deployment_id": str(uuid4()), "environment": "production"},
                    params={"replicas": 2, "estimated_cost_per_hour": 20},
                    ttl=900,
                ),
            ],
            source=ActionPlanSource.USER,
            created_at=datetime.utcnow(),
        )

        result = engine.evaluate(prod_plan)
        assert result.approved is False  # Should violate cost ceiling

        # Plan targeting dev - should not be evaluated against production policy
        dev_plan = ActionPlan(
            id=uuid4(),
            decisions=[
                Decision(
                    verb=DecisionVerb.SCALE,
                    target={"deployment_id": str(uuid4()), "environment": "dev"},
                    params={"replicas": 2, "estimated_cost_per_hour": 20},
                    ttl=900,
                ),
            ],
            source=ActionPlanSource.USER,
            created_at=datetime.utcnow(),
        )

        result = engine.evaluate(dev_plan)
        assert result.approved is True  # No matching policy

    def test_evaluation_duration_tracking(self, sample_policy, sample_action_plan):
        """Test that evaluation duration is tracked."""
        engine = PolicyEngine()
        engine.register_policy(sample_policy)

        result = engine.evaluate(sample_action_plan)

        assert result.duration_ms > 0
        assert result.evaluated_at is not None

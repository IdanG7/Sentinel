"""Pytest configuration and fixtures for Policy Engine tests."""

import pytest
from datetime import datetime
from uuid import uuid4

from sentinel_policy import (
    ActionPlan,
    ActionPlanSource,
    Decision,
    DecisionVerb,
    Policy,
    PolicyRule,
    PolicyRuleType,
)


@pytest.fixture
def sample_policy():
    """Sample policy for testing."""
    return Policy(
        id=uuid4(),
        name="Test Policy",
        rules=[
            PolicyRule(
                type=PolicyRuleType.COST_CEILING,
                constraint={"max_cost_per_hour": 100, "currency": "USD"},
                action_on_violation="reject",
            ),
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


@pytest.fixture
def sample_sla_policy():
    """Sample SLA policy for testing."""
    return Policy(
        id=uuid4(),
        name="SLA Policy",
        rules=[
            PolicyRule(
                type=PolicyRuleType.SLA,
                constraint={"min_uptime_percent": 99.9, "measurement_window_hours": 720},
                action_on_violation="reject",
            ),
        ],
        priority=200,
        enabled=True,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )


@pytest.fixture
def sample_action_plan():
    """Sample action plan for testing."""
    return ActionPlan(
        id=uuid4(),
        decisions=[
            Decision(
                verb=DecisionVerb.SCALE,
                target={"deployment_id": str(uuid4()), "cluster": "prod"},
                params={"replicas": 5, "estimated_cost_per_hour": 50},
                ttl=900,
            ),
        ],
        source=ActionPlanSource.USER,
        created_at=datetime.utcnow(),
    )


@pytest.fixture
def violating_action_plan():
    """Action plan that violates cost ceiling only."""
    return ActionPlan(
        id=uuid4(),
        decisions=[
            Decision(
                verb=DecisionVerb.SCALE,
                target={"deployment_id": str(uuid4()), "cluster": "prod"},
                params={"replicas": 5, "estimated_cost_per_hour": 150},  # Only cost exceeds
                ttl=900,
            ),
        ],
        source=ActionPlanSource.INFRAMIND,
        created_at=datetime.utcnow(),
    )


@pytest.fixture
def quota_violating_action_plan():
    """Action plan that violates quota."""
    return ActionPlan(
        id=uuid4(),
        decisions=[
            Decision(
                verb=DecisionVerb.SCALE,
                target={"deployment_id": str(uuid4())},
                params={"replicas": 15, "total_gpus": 8},  # Exceeds limits
                ttl=900,
            ),
        ],
        source=ActionPlanSource.USER,
        created_at=datetime.utcnow(),
    )

"""Tests for change freeze window enforcement."""

import pytest
from datetime import datetime, timedelta
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


class TestChangeFreezeWindows:
    """Test change freeze window enforcement."""

    def test_absolute_freeze_window_blocks_changes(self):
        """Test that absolute freeze window blocks changes during the window."""
        engine = PolicyEngine(mode=EvaluationMode.ENFORCE)

        # Create freeze window that is currently active
        now = datetime.utcnow()
        start = (now - timedelta(hours=1)).isoformat() + "Z"
        end = (now + timedelta(hours=1)).isoformat() + "Z"

        policy = Policy(
            id=uuid4(),
            name="Holiday Freeze",
            rules=[
                PolicyRule(
                    type=PolicyRuleType.CHANGE_FREEZE,
                    constraint={
                        "freeze_windows": [
                            {
                                "start": start,
                                "end": end,
                                "reason": "Black Friday freeze",
                                "timezone": "UTC",
                            }
                        ]
                    },
                    action_on_violation="reject",
                ),
            ],
            priority=100,
            enabled=True,
            created_at=now,
            updated_at=now,
        )

        engine.register_policy(policy)

        # Create action plan during freeze window
        plan = ActionPlan(
            id=uuid4(),
            decisions=[
                Decision(
                    verb=DecisionVerb.SCALE,
                    target={"deployment_id": str(uuid4())},
                    params={"replicas": 5},
                    ttl=900,
                ),
            ],
            source=ActionPlanSource.INFRAMIND,
            created_at=now,
        )

        result = engine.evaluate(plan)

        # Should be rejected due to freeze window
        assert result.approved is False
        assert len(result.violations) == 1
        assert result.violations[0].rule_type == PolicyRuleType.CHANGE_FREEZE
        assert "Black Friday freeze" in result.violations[0].message

    def test_freeze_window_allows_changes_outside_window(self):
        """Test that freeze window allows changes outside the window."""
        engine = PolicyEngine(mode=EvaluationMode.ENFORCE)

        now = datetime.utcnow()
        # Create freeze window in the future
        start = (now + timedelta(days=1)).isoformat() + "Z"
        end = (now + timedelta(days=2)).isoformat() + "Z"

        policy = Policy(
            id=uuid4(),
            name="Future Freeze",
            rules=[
                PolicyRule(
                    type=PolicyRuleType.CHANGE_FREEZE,
                    constraint={
                        "freeze_windows": [
                            {
                                "start": start,
                                "end": end,
                                "reason": "Upcoming freeze",
                                "timezone": "UTC",
                            }
                        ]
                    },
                    action_on_violation="reject",
                ),
            ],
            priority=100,
            enabled=True,
            created_at=now,
            updated_at=now,
        )

        engine.register_policy(policy)

        plan = ActionPlan(
            id=uuid4(),
            decisions=[
                Decision(
                    verb=DecisionVerb.SCALE,
                    target={"deployment_id": str(uuid4())},
                    params={"replicas": 5},
                    ttl=900,
                ),
            ],
            source=ActionPlanSource.INFRAMIND,
            created_at=now,
        )

        result = engine.evaluate(plan)

        # Should be approved - outside freeze window
        assert result.approved is True
        assert len(result.violations) == 0

    def test_recurring_freeze_by_day_of_week(self):
        """Test recurring freeze by day of week."""
        engine = PolicyEngine(mode=EvaluationMode.ENFORCE)

        now = datetime.utcnow()
        current_day = now.weekday()  # 0=Monday, 6=Sunday

        policy = Policy(
            id=uuid4(),
            name="Weekend Freeze",
            rules=[
                PolicyRule(
                    type=PolicyRuleType.CHANGE_FREEZE,
                    constraint={
                        "recurring": {
                            "days_of_week": [current_day],  # Current day
                            "timezone": "UTC",
                        }
                    },
                    action_on_violation="reject",
                ),
            ],
            priority=100,
            enabled=True,
            created_at=now,
            updated_at=now,
        )

        engine.register_policy(policy)

        plan = ActionPlan(
            id=uuid4(),
            decisions=[
                Decision(
                    verb=DecisionVerb.SCALE,
                    target={"deployment_id": str(uuid4())},
                    params={"replicas": 5},
                    ttl=900,
                ),
            ],
            source=ActionPlanSource.INFRAMIND,
            created_at=now,
        )

        result = engine.evaluate(plan)

        # Should be rejected - current day is in freeze
        assert result.approved is False
        assert len(result.violations) == 1
        assert result.violations[0].rule_type == PolicyRuleType.CHANGE_FREEZE

    def test_exempt_sources_bypass_freeze(self):
        """Test that exempt sources can make changes during freeze."""
        engine = PolicyEngine(mode=EvaluationMode.ENFORCE)

        now = datetime.utcnow()
        start = (now - timedelta(hours=1)).isoformat() + "Z"
        end = (now + timedelta(hours=1)).isoformat() + "Z"

        policy = Policy(
            id=uuid4(),
            name="Freeze with Exemptions",
            rules=[
                PolicyRule(
                    type=PolicyRuleType.CHANGE_FREEZE,
                    constraint={
                        "freeze_windows": [
                            {
                                "start": start,
                                "end": end,
                                "reason": "Freeze",
                                "timezone": "UTC",
                            }
                        ],
                        "exempt_sources": ["user"],  # Exempt user-initiated changes
                    },
                    action_on_violation="reject",
                ),
            ],
            priority=100,
            enabled=True,
            created_at=now,
            updated_at=now,
        )

        engine.register_policy(policy)

        # Create plan with exempt source
        plan = ActionPlan(
            id=uuid4(),
            decisions=[
                Decision(
                    verb=DecisionVerb.SCALE,
                    target={"deployment_id": str(uuid4())},
                    params={"replicas": 5, "source": "user"},  # Exempt source
                    ttl=900,
                ),
            ],
            source=ActionPlanSource.USER,
            created_at=now,
        )

        result = engine.evaluate(plan)

        # Should be approved - source is exempt
        assert result.approved is True
        assert len(result.violations) == 0

    def test_multiple_freeze_windows(self):
        """Test policy with multiple freeze windows."""
        engine = PolicyEngine(mode=EvaluationMode.ENFORCE)

        now = datetime.utcnow()

        # First window: past
        window1_start = (now - timedelta(days=2)).isoformat() + "Z"
        window1_end = (now - timedelta(days=1)).isoformat() + "Z"

        # Second window: active now
        window2_start = (now - timedelta(hours=1)).isoformat() + "Z"
        window2_end = (now + timedelta(hours=1)).isoformat() + "Z"

        policy = Policy(
            id=uuid4(),
            name="Multiple Freezes",
            rules=[
                PolicyRule(
                    type=PolicyRuleType.CHANGE_FREEZE,
                    constraint={
                        "freeze_windows": [
                            {
                                "start": window1_start,
                                "end": window1_end,
                                "reason": "Past freeze",
                                "timezone": "UTC",
                            },
                            {
                                "start": window2_start,
                                "end": window2_end,
                                "reason": "Current freeze",
                                "timezone": "UTC",
                            },
                        ]
                    },
                    action_on_violation="reject",
                ),
            ],
            priority=100,
            enabled=True,
            created_at=now,
            updated_at=now,
        )

        engine.register_policy(policy)

        plan = ActionPlan(
            id=uuid4(),
            decisions=[
                Decision(
                    verb=DecisionVerb.SCALE,
                    target={"deployment_id": str(uuid4())},
                    params={"replicas": 5},
                    ttl=900,
                ),
            ],
            source=ActionPlanSource.INFRAMIND,
            created_at=now,
        )

        result = engine.evaluate(plan)

        # Should be rejected due to second window
        assert result.approved is False
        assert len(result.violations) == 1
        assert "Current freeze" in result.violations[0].message

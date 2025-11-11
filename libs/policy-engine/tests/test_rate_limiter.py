"""Tests for rate limiter."""

import pytest
import time
from datetime import datetime
from uuid import uuid4

from sentinel_policy import (
    RateLimiter,
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


class TestRateLimiter:
    """Test rate limiter functionality."""

    def test_rate_limiter_basic(self):
        """Test basic rate limiting."""
        limiter = RateLimiter()

        # First request should be allowed
        allowed, metadata = limiter.check_rate_limit(
            resource_key="test-resource",
            max_operations=5,
            window_seconds=60,
        )

        assert allowed is True
        assert metadata["current_count"] == 0
        assert metadata["limit"] == 5
        assert metadata["remaining"] == 4

    def test_rate_limiter_enforces_limit(self):
        """Test that rate limiter enforces limits."""
        limiter = RateLimiter()
        resource_key = "test-workload"
        max_ops = 3
        window = 60

        # Make requests up to limit
        for i in range(max_ops):
            allowed, metadata = limiter.check_rate_limit(
                resource_key, max_ops, window
            )
            assert allowed is True
            assert metadata["current_count"] == i
            assert metadata["remaining"] == max_ops - (i + 1)

        # Next request should be blocked
        allowed, metadata = limiter.check_rate_limit(resource_key, max_ops, window)
        assert allowed is False
        assert metadata["current_count"] == max_ops
        assert metadata["remaining"] == 0

    def test_rate_limiter_sliding_window(self):
        """Test sliding window behavior."""
        limiter = RateLimiter()
        resource_key = "test-resource"

        # Fill up the limit
        for _ in range(3):
            allowed, _ = limiter.check_rate_limit(resource_key, 3, 1)  # 1 second window
            assert allowed is True

        # Should be blocked immediately
        allowed, _ = limiter.check_rate_limit(resource_key, 3, 1)
        assert allowed is False

        # Wait for window to expire
        time.sleep(1.1)

        # Should be allowed again
        allowed, _ = limiter.check_rate_limit(resource_key, 3, 1)
        assert allowed is True

    def test_rate_limiter_per_resource(self):
        """Test that rate limits are per-resource."""
        limiter = RateLimiter()

        # Fill up limit for resource A
        for _ in range(3):
            allowed, _ = limiter.check_rate_limit("resource-a", 3, 60)
            assert allowed is True

        # Resource A should be blocked
        allowed, _ = limiter.check_rate_limit("resource-a", 3, 60)
        assert allowed is False

        # Resource B should still be allowed
        allowed, _ = limiter.check_rate_limit("resource-b", 3, 60)
        assert allowed is True

    def test_rate_limiter_get_current_count(self):
        """Test getting current operation count."""
        limiter = RateLimiter()
        resource_key = "test-resource"
        window = 60

        # Initially zero
        count = limiter.get_current_count(resource_key, window)
        assert count == 0

        # Add some operations
        for i in range(3):
            limiter.check_rate_limit(resource_key, 10, window)
            count = limiter.get_current_count(resource_key, window)
            assert count == i + 1

    def test_rate_limiter_reset(self):
        """Test rate limiter reset."""
        limiter = RateLimiter()
        resource_key = "test-resource"

        # Add operations
        for _ in range(3):
            limiter.check_rate_limit(resource_key, 5, 60)

        count = limiter.get_current_count(resource_key, 60)
        assert count == 3

        # Reset specific resource
        limiter.reset(resource_key)
        count = limiter.get_current_count(resource_key, 60)
        assert count == 0

    def test_rate_limiter_reset_all(self):
        """Test resetting all rate limits."""
        limiter = RateLimiter()

        # Add operations to multiple resources
        for i in range(3):
            limiter.check_rate_limit(f"resource-{i}", 5, 60)

        # Reset all
        limiter.reset()

        # All counts should be zero
        for i in range(3):
            count = limiter.get_current_count(f"resource-{i}", 60)
            assert count == 0

    def test_rate_limiter_cleanup(self):
        """Test cleanup of expired entries."""
        limiter = RateLimiter()

        # Add operations
        for i in range(5):
            limiter.check_rate_limit(f"resource-{i}", 10, 1)  # 1 second window

        # Wait for expiration
        time.sleep(1.1)

        # Cleanup should remove old entries
        removed = limiter.cleanup_expired(max_age_seconds=1)
        assert removed >= 5

    def test_rate_limiter_increment(self):
        """Test custom increment values."""
        limiter = RateLimiter()
        resource_key = "test-resource"

        # Add with increment of 3
        allowed, metadata = limiter.check_rate_limit(
            resource_key, max_operations=10, window_seconds=60, increment=3
        )
        assert allowed is True
        assert metadata["current_count"] == 0  # Count before increment

        # Next check should show count of 3
        count = limiter.get_current_count(resource_key, 60)
        assert count == 3

        # Add another 8 (total would be 11, over limit of 10)
        allowed, metadata = limiter.check_rate_limit(
            resource_key, max_operations=10, window_seconds=60, increment=8
        )
        assert allowed is False


class TestRateLimitPolicy:
    """Test rate limiting in policy engine."""

    def test_rate_limit_policy_per_minute(self):
        """Test per-minute rate limit policy."""
        engine = PolicyEngine(mode=EvaluationMode.ENFORCE)

        policy = Policy(
            id=uuid4(),
            name="Rate Limit Policy",
            rules=[
                PolicyRule(
                    type=PolicyRuleType.RATE_LIMIT,
                    constraint={
                        "max_operations_per_minute": 3,
                        "scope": "workload",
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

        # Create plans for the same workload
        workload_id = str(uuid4())

        # First 3 should be allowed
        for i in range(3):
            plan = ActionPlan(
                id=uuid4(),
                decisions=[
                    Decision(
                        verb=DecisionVerb.SCALE,
                        target={"workload": f"workload-{workload_id}"},
                        params={"replicas": 5},
                        ttl=900,
                    ),
                ],
                source=ActionPlanSource.INFRAMIND,
                created_at=datetime.utcnow(),
            )

            result = engine.evaluate(plan)
            assert result.approved is True, f"Request {i+1} should be approved"

        # 4th should be blocked
        plan = ActionPlan(
            id=uuid4(),
            decisions=[
                Decision(
                    verb=DecisionVerb.SCALE,
                    target={"workload": f"workload-{workload_id}"},
                    params={"replicas": 5},
                    ttl=900,
                ),
            ],
            source=ActionPlanSource.INFRAMIND,
            created_at=datetime.utcnow(),
        )

        result = engine.evaluate(plan)
        assert result.approved is False
        assert len(result.violations) == 1
        assert result.violations[0].rule_type == PolicyRuleType.RATE_LIMIT

    def test_rate_limit_different_scopes(self):
        """Test rate limiting with different scopes."""
        engine = PolicyEngine(mode=EvaluationMode.ENFORCE)

        # Workload-scoped rate limit
        policy = Policy(
            id=uuid4(),
            name="Workload Rate Limit",
            rules=[
                PolicyRule(
                    type=PolicyRuleType.RATE_LIMIT,
                    constraint={
                        "max_operations_per_minute": 2,
                        "scope": "workload",
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

        # Different workloads should have separate limits
        for workload_num in range(3):
            for _ in range(2):
                plan = ActionPlan(
                    id=uuid4(),
                    decisions=[
                        Decision(
                            verb=DecisionVerb.SCALE,
                            target={"workload": f"workload-{workload_num}"},
                            params={"replicas": 5},
                            ttl=900,
                        ),
                    ],
                    source=ActionPlanSource.INFRAMIND,
                    created_at=datetime.utcnow(),
                )

                result = engine.evaluate(plan)
                assert result.approved is True  # Each workload gets its own limit

    def test_rate_limit_global_scope(self):
        """Test global rate limiting."""
        engine = PolicyEngine(mode=EvaluationMode.ENFORCE)

        policy = Policy(
            id=uuid4(),
            name="Global Rate Limit",
            rules=[
                PolicyRule(
                    type=PolicyRuleType.RATE_LIMIT,
                    constraint={
                        "max_operations_per_minute": 3,
                        "scope": "global",
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

        # Make requests for different workloads
        for i in range(3):
            plan = ActionPlan(
                id=uuid4(),
                decisions=[
                    Decision(
                        verb=DecisionVerb.SCALE,
                        target={"workload": f"workload-{i}"},
                        params={"replicas": 5},
                        ttl=900,
                    ),
                ],
                source=ActionPlanSource.INFRAMIND,
                created_at=datetime.utcnow(),
            )

            result = engine.evaluate(plan)
            assert result.approved is True

        # 4th request should be blocked (global limit reached)
        plan = ActionPlan(
            id=uuid4(),
            decisions=[
                Decision(
                    verb=DecisionVerb.SCALE,
                    target={"workload": "another-workload"},
                    params={"replicas": 5},
                    ttl=900,
                ),
            ],
            source=ActionPlanSource.INFRAMIND,
            created_at=datetime.utcnow(),
        )

        result = engine.evaluate(plan)
        assert result.approved is False
        assert result.violations[0].rule_type == PolicyRuleType.RATE_LIMIT

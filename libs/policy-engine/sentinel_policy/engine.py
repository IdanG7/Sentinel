"""Policy evaluation engine for Sentinel."""

import logging
from datetime import datetime
from enum import Enum
from typing import Any, Optional

from .models import (
    ActionPlan,
    Decision,
    Policy,
    PolicyEvaluationResult,
    PolicyRule,
    PolicyRuleType,
    PolicyViolation,
)
from .rate_limiter import RateLimiter

logger = logging.getLogger(__name__)


class EvaluationMode(str, Enum):
    """Policy evaluation mode."""

    ENFORCE = "enforce"
    DRY_RUN = "dry_run"
    AUDIT = "audit"
    SHADOW = "shadow"  # Full simulation without execution


class PolicyEngine:
    """
    Policy evaluation engine.

    Evaluates action plans against registered policies and enforces constraints.
    """

    def __init__(
        self, mode: EvaluationMode = EvaluationMode.ENFORCE, rate_limiter: RateLimiter | None = None
    ):
        """
        Initialize policy engine.

        Args:
            mode: Evaluation mode (enforce, dry_run, audit, shadow)
            rate_limiter: Rate limiter instance (creates new one if not provided)
        """
        self.mode = mode
        self._policies: dict[str, Policy] = {}
        self._rate_limiter = rate_limiter or RateLimiter()
        logger.info(f"Policy engine initialized in {mode} mode")

    def register_policy(self, policy: Policy) -> None:
        """
        Register a policy for evaluation.

        Args:
            policy: Policy to register
        """
        self._policies[str(policy.id)] = policy
        logger.info(f"Registered policy: {policy.name} (priority: {policy.priority})")

    def unregister_policy(self, policy_id: str) -> bool:
        """
        Unregister a policy.

        Args:
            policy_id: Policy ID to unregister

        Returns:
            True if policy was unregistered, False if not found
        """
        if policy_id in self._policies:
            policy = self._policies.pop(policy_id)
            logger.info(f"Unregistered policy: {policy.name}")
            return True
        return False

    def get_policy(self, policy_id: str) -> Optional[Policy]:
        """
        Get a policy by ID.

        Args:
            policy_id: Policy ID

        Returns:
            Policy or None if not found
        """
        return self._policies.get(policy_id)

    def list_policies(self, enabled_only: bool = False) -> list[Policy]:
        """
        List all registered policies.

        Args:
            enabled_only: Only return enabled policies

        Returns:
            List of policies sorted by priority (highest first)
        """
        policies = list(self._policies.values())
        if enabled_only:
            policies = [p for p in policies if p.enabled]
        return sorted(policies, key=lambda p: p.priority, reverse=True)

    def evaluate(self, action_plan: ActionPlan) -> PolicyEvaluationResult:
        """
        Evaluate an action plan against all registered policies.

        Args:
            action_plan: Action plan to evaluate

        Returns:
            PolicyEvaluationResult with verdict and violations
        """
        start_time = datetime.utcnow()
        violations: list[PolicyViolation] = []

        # Get enabled policies sorted by priority
        policies = self.list_policies(enabled_only=True)

        logger.info(
            f"Evaluating action plan {action_plan.id} against {len(policies)} policies"
        )

        # Evaluate each decision against each policy
        for decision in action_plan.decisions:
            for policy in policies:
                # Check if policy selector matches the decision target
                if not self._matches_selector(decision, policy):
                    continue

                # Evaluate each rule in the policy
                for rule in policy.rules:
                    violation = self._evaluate_rule(decision, rule, policy)
                    if violation:
                        violations.append(violation)
                        logger.warning(
                            f"Policy violation: {policy.name} - {violation.message}"
                        )

        # Determine verdict
        approved = (
            len(violations) == 0
            or self.mode == EvaluationMode.DRY_RUN
            or self.mode == EvaluationMode.SHADOW
        )

        # In dry-run or shadow mode, log violations but don't reject
        if self.mode == EvaluationMode.DRY_RUN and violations:
            logger.info(
                f"DRY RUN: Action plan would be rejected with {len(violations)} violations"
            )
        elif self.mode == EvaluationMode.SHADOW:
            logger.info(
                f"SHADOW MODE: Simulating action plan execution "
                f"({'would be rejected' if violations else 'would succeed'} "
                f"with {len(violations)} violations)"
            )

        # Calculate evaluation duration
        duration_ms = (datetime.utcnow() - start_time).total_seconds() * 1000

        result = PolicyEvaluationResult(
            action_plan_id=action_plan.id,
            approved=approved,
            violations=violations,
            evaluated_at=datetime.utcnow(),
            mode=self.mode,
            duration_ms=duration_ms,
        )

        logger.info(
            f"Evaluation complete: {'APPROVED' if approved else 'REJECTED'} "
            f"({len(violations)} violations, {duration_ms:.2f}ms)"
        )

        return result

    def _matches_selector(self, decision: Decision, policy: Policy) -> bool:
        """
        Check if a policy selector matches a decision target.

        Args:
            decision: Decision to check
            policy: Policy with selector

        Returns:
            True if selector matches
        """
        # If no selector, policy applies to all decisions
        if not policy.selector:
            return True

        # Check if all selector labels match decision target labels
        for key, value in policy.selector.items():
            if decision.target.get(key) != value:
                return False

        return True

    def _evaluate_rule(
        self, decision: Decision, rule: PolicyRule, policy: Policy
    ) -> Optional[PolicyViolation]:
        """
        Evaluate a single rule against a decision.

        Args:
            decision: Decision to evaluate
            rule: Policy rule to check
            policy: Parent policy

        Returns:
            PolicyViolation if rule is violated, None otherwise
        """
        rule_type = rule.type

        if rule_type == PolicyRuleType.COST_CEILING:
            return self._check_cost_ceiling(decision, rule, policy)
        elif rule_type == PolicyRuleType.RATE_LIMIT:
            return self._check_rate_limit(decision, rule, policy)
        elif rule_type == PolicyRuleType.SLA:
            return self._check_sla(decision, rule, policy)
        elif rule_type == PolicyRuleType.SLO:
            return self._check_slo(decision, rule, policy)
        elif rule_type == PolicyRuleType.QUOTA:
            return self._check_quota(decision, rule, policy)
        elif rule_type == PolicyRuleType.CHANGE_FREEZE:
            return self._check_change_freeze(decision, rule, policy)
        else:
            logger.warning(f"Unknown rule type: {rule_type}")
            return None

    def _check_cost_ceiling(
        self, decision: Decision, rule: PolicyRule, policy: Policy
    ) -> Optional[PolicyViolation]:
        """
        Check if decision violates cost ceiling constraint.

        Constraint format: {"max_cost_per_hour": 100, "currency": "USD"}
        """
        max_cost = rule.constraint.get("max_cost_per_hour")
        if max_cost is None:
            return None

        # Get estimated cost from decision params
        estimated_cost = decision.params.get("estimated_cost_per_hour")
        if estimated_cost is None:
            # If no cost estimate, assume it's within limits
            return None

        if estimated_cost > max_cost:
            currency = rule.constraint.get("currency", "USD")
            return PolicyViolation(
                policy_id=policy.id,
                policy_name=policy.name,
                rule_type=rule.type,
                message=f"Cost ceiling exceeded: {estimated_cost} {currency}/hour > {max_cost} {currency}/hour",
                decision_verb=decision.verb,
                decision_target=decision.target,
                action=rule.action_on_violation,
            )

        return None

    def _check_rate_limit(
        self, decision: Decision, rule: PolicyRule, policy: Policy
    ) -> Optional[PolicyViolation]:
        """
        Check if decision violates rate limit constraint.

        Constraint format: {
            "max_operations_per_minute": 10,
            "max_operations_per_hour": 100,
            "scope": "workload"  # or "cluster", "namespace", "global"
        }
        """
        # Build resource key based on scope
        scope = rule.constraint.get("scope", "workload")
        if scope == "workload":
            resource_key = decision.target.get("workload") or decision.target.get("deployment_id")
        elif scope == "cluster":
            resource_key = f"cluster:{decision.target.get('cluster', 'default')}"
        elif scope == "namespace":
            resource_key = f"namespace:{decision.target.get('namespace', 'default')}"
        else:  # global
            resource_key = "global"

        if not resource_key:
            logger.warning("Cannot determine resource key for rate limiting")
            return None

        # Check per-minute limit
        max_ops_per_min = rule.constraint.get("max_operations_per_minute")
        if max_ops_per_min:
            allowed, metadata = self._rate_limiter.check_rate_limit(
                resource_key=f"{resource_key}:minute",
                max_operations=max_ops_per_min,
                window_seconds=60,
            )
            if not allowed:
                return PolicyViolation(
                    policy_id=policy.id,
                    policy_name=policy.name,
                    rule_type=rule.type,
                    message=f"Rate limit exceeded: {metadata['current_count']} operations/minute > {max_ops_per_min} (scope: {scope})",
                    decision_verb=decision.verb,
                    decision_target=decision.target,
                    action=rule.action_on_violation,
                )

        # Check per-hour limit
        max_ops_per_hour = rule.constraint.get("max_operations_per_hour")
        if max_ops_per_hour:
            allowed, metadata = self._rate_limiter.check_rate_limit(
                resource_key=f"{resource_key}:hour",
                max_operations=max_ops_per_hour,
                window_seconds=3600,
            )
            if not allowed:
                return PolicyViolation(
                    policy_id=policy.id,
                    policy_name=policy.name,
                    rule_type=rule.type,
                    message=f"Rate limit exceeded: {metadata['current_count']} operations/hour > {max_ops_per_hour} (scope: {scope})",
                    decision_verb=decision.verb,
                    decision_target=decision.target,
                    action=rule.action_on_violation,
                )

        return None

    def _check_sla(
        self, decision: Decision, rule: PolicyRule, policy: Policy
    ) -> Optional[PolicyViolation]:
        """
        Check if decision violates SLA constraint.

        Constraint format: {
            "min_uptime_percent": 99.9,
            "measurement_window_hours": 720  # 30 days
        }
        """
        min_uptime = rule.constraint.get("min_uptime_percent")
        if min_uptime is None:
            return None

        # Get current uptime from decision metadata
        current_uptime = decision.params.get("current_uptime_percent")
        if current_uptime is None:
            # If no uptime data, assume SLA is met
            return None

        # Check if the action would violate SLA
        # For scale-down or drain operations, check if remaining capacity meets SLA
        if decision.verb in ["scale", "drain"] and current_uptime < min_uptime:
            return PolicyViolation(
                policy_id=policy.id,
                policy_name=policy.name,
                rule_type=rule.type,
                message=f"SLA violation risk: Current uptime {current_uptime}% < {min_uptime}%",
                decision_verb=decision.verb,
                decision_target=decision.target,
                action=rule.action_on_violation,
            )

        return None

    def _check_slo(
        self, decision: Decision, rule: PolicyRule, policy: Policy
    ) -> Optional[PolicyViolation]:
        """
        Check if decision violates SLO constraint.

        Constraint format: {
            "max_p99_latency_ms": 500,
            "min_success_rate_percent": 99.5
        }
        """
        # Check latency SLO
        max_latency = rule.constraint.get("max_p99_latency_ms")
        if max_latency:
            current_latency = decision.params.get("current_p99_latency_ms")
            if current_latency and current_latency > max_latency:
                return PolicyViolation(
                    policy_id=policy.id,
                    policy_name=policy.name,
                    rule_type=rule.type,
                    message=f"Latency SLO violation: p99 {current_latency}ms > {max_latency}ms",
                    decision_verb=decision.verb,
                    decision_target=decision.target,
                    action=rule.action_on_violation,
                )

        # Check success rate SLO
        min_success_rate = rule.constraint.get("min_success_rate_percent")
        if min_success_rate:
            current_success_rate = decision.params.get("current_success_rate_percent")
            if current_success_rate and current_success_rate < min_success_rate:
                return PolicyViolation(
                    policy_id=policy.id,
                    policy_name=policy.name,
                    rule_type=rule.type,
                    message=f"Success rate SLO violation: {current_success_rate}% < {min_success_rate}%",
                    decision_verb=decision.verb,
                    decision_target=decision.target,
                    action=rule.action_on_violation,
                )

        return None

    def _check_quota(
        self, decision: Decision, rule: PolicyRule, policy: Policy
    ) -> Optional[PolicyViolation]:
        """
        Check if decision violates resource quota constraint.

        Constraint format: {
            "max_replicas": 100,
            "max_cpu_cores": 500,
            "max_memory_gi": 2000,
            "max_gpus": 50
        }
        """
        # Check replica quota
        max_replicas = rule.constraint.get("max_replicas")
        if max_replicas and decision.verb == "scale":
            target_replicas = decision.params.get("replicas")
            if target_replicas and target_replicas > max_replicas:
                return PolicyViolation(
                    policy_id=policy.id,
                    policy_name=policy.name,
                    rule_type=rule.type,
                    message=f"Replica quota exceeded: {target_replicas} > {max_replicas}",
                    decision_verb=decision.verb,
                    decision_target=decision.target,
                    action=rule.action_on_violation,
                )

        # Check CPU quota
        max_cpu = rule.constraint.get("max_cpu_cores")
        if max_cpu:
            requested_cpu = decision.params.get("total_cpu_cores")
            if requested_cpu and requested_cpu > max_cpu:
                return PolicyViolation(
                    policy_id=policy.id,
                    policy_name=policy.name,
                    rule_type=rule.type,
                    message=f"CPU quota exceeded: {requested_cpu} cores > {max_cpu} cores",
                    decision_verb=decision.verb,
                    decision_target=decision.target,
                    action=rule.action_on_violation,
                )

        # Check memory quota
        max_memory = rule.constraint.get("max_memory_gi")
        if max_memory:
            requested_memory = decision.params.get("total_memory_gi")
            if requested_memory and requested_memory > max_memory:
                return PolicyViolation(
                    policy_id=policy.id,
                    policy_name=policy.name,
                    rule_type=rule.type,
                    message=f"Memory quota exceeded: {requested_memory}Gi > {max_memory}Gi",
                    decision_verb=decision.verb,
                    decision_target=decision.target,
                    action=rule.action_on_violation,
                )

        # Check GPU quota
        max_gpus = rule.constraint.get("max_gpus")
        if max_gpus:
            requested_gpus = decision.params.get("total_gpus")
            if requested_gpus and requested_gpus > max_gpus:
                return PolicyViolation(
                    policy_id=policy.id,
                    policy_name=policy.name,
                    rule_type=rule.type,
                    message=f"GPU quota exceeded: {requested_gpus} > {max_gpus}",
                    decision_verb=decision.verb,
                    decision_target=decision.target,
                    action=rule.action_on_violation,
                )

        return None

    def _check_change_freeze(
        self, decision: Decision, rule: PolicyRule, policy: Policy
    ) -> Optional[PolicyViolation]:
        """
        Check if decision violates change freeze window.

        Constraint format: {
            "freeze_windows": [
                {
                    "start": "2025-11-11T00:00:00Z",
                    "end": "2025-11-12T00:00:00Z",
                    "reason": "Holiday freeze",
                    "timezone": "UTC"
                }
            ],
            "recurring": {
                "days_of_week": [6, 0],  # Saturday=6, Sunday=0
                "hours": [22, 23, 0, 1, 2, 3, 4, 5],
                "timezone": "UTC"
            },
            "exempt_sources": ["user"]  # Exempt user-initiated changes
        }
        """
        from datetime import datetime as dt
        import pytz

        now = dt.utcnow().replace(tzinfo=pytz.UTC)

        # Check if source is exempt
        exempt_sources = rule.constraint.get("exempt_sources", [])
        decision_source = decision.params.get("source")
        if decision_source and decision_source in exempt_sources:
            return None

        # Check absolute freeze windows
        freeze_windows = rule.constraint.get("freeze_windows", [])
        for window in freeze_windows:
            try:
                start = dt.fromisoformat(window["start"].replace("Z", "+00:00"))
                end = dt.fromisoformat(window["end"].replace("Z", "+00:00"))
                timezone = pytz.timezone(window.get("timezone", "UTC"))

                # Convert to specified timezone
                start = start.astimezone(timezone)
                end = end.astimezone(timezone)
                now_tz = now.astimezone(timezone)

                if start <= now_tz <= end:
                    reason = window.get("reason", "Change freeze window")
                    return PolicyViolation(
                        policy_id=policy.id,
                        policy_name=policy.name,
                        rule_type=rule.type,
                        message=f"Change freeze active: {reason} ({start} - {end})",
                        decision_verb=decision.verb,
                        decision_target=decision.target,
                        action=rule.action_on_violation,
                    )
            except (KeyError, ValueError) as e:
                logger.warning(f"Invalid freeze window configuration: {e}")
                continue

        # Check recurring freeze windows
        recurring = rule.constraint.get("recurring")
        if recurring:
            timezone = pytz.timezone(recurring.get("timezone", "UTC"))
            now_tz = now.astimezone(timezone)

            # Check day of week (0=Monday, 6=Sunday)
            days_of_week = recurring.get("days_of_week", [])
            if days_of_week and now_tz.weekday() in days_of_week:
                return PolicyViolation(
                    policy_id=policy.id,
                    policy_name=policy.name,
                    rule_type=rule.type,
                    message=f"Recurring freeze: Changes not allowed on {now_tz.strftime('%A')}",
                    decision_verb=decision.verb,
                    decision_target=decision.target,
                    action=rule.action_on_violation,
                )

            # Check hour of day
            hours = recurring.get("hours", [])
            if hours and now_tz.hour in hours:
                return PolicyViolation(
                    policy_id=policy.id,
                    policy_name=policy.name,
                    rule_type=rule.type,
                    message=f"Recurring freeze: Changes not allowed at {now_tz.hour}:00",
                    decision_verb=decision.verb,
                    decision_target=decision.target,
                    action=rule.action_on_violation,
                )

        return None

"""Data models for the policy engine."""

from datetime import datetime
from enum import Enum
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class PolicyRuleType(str, Enum):
    """Policy rule type enumeration."""

    COST_CEILING = "cost_ceiling"
    RATE_LIMIT = "rate_limit"
    SLA = "sla"
    SLO = "slo"
    QUOTA = "quota"


class PolicyRule(BaseModel):
    """
    Policy rule definition.

    Rules define constraints that must be satisfied by decisions.
    """

    type: PolicyRuleType
    constraint: dict[str, Any] = Field(
        ..., description="Constraint parameters specific to rule type"
    )
    action_on_violation: str = Field(
        default="reject",
        description="Action to take on violation: reject, warn, log",
    )


class Policy(BaseModel):
    """
    Policy definition.

    A policy is a collection of rules that govern decision-making.
    """

    id: UUID
    name: str = Field(..., min_length=3, max_length=255)
    rules: list[PolicyRule]
    priority: int = Field(default=0, ge=0, le=1000, description="Higher = evaluated first")
    enabled: bool = True
    selector: Optional[dict[str, str]] = Field(
        default=None, description="Label selector to match decisions"
    )
    created_at: datetime
    updated_at: datetime


class DecisionVerb(str, Enum):
    """Decision verb enumeration."""

    SCALE = "scale"
    RESCHEDULE = "reschedule"
    ROLLBACK = "rollback"
    RESTART = "restart"
    DRAIN = "drain"


class Decision(BaseModel):
    """
    Decision represents a single action to be taken.

    Decisions are evaluated against policies before execution.
    """

    verb: DecisionVerb
    target: dict[str, str] = Field(..., description="Target resource identifiers")
    params: dict[str, Any] = Field(..., description="Action parameters")
    ttl: int = Field(
        default=900, ge=60, le=3600, description="Time-to-live in seconds"
    )
    safety: Optional[dict[str, Any]] = Field(
        default=None, description="Safety constraints for the decision"
    )


class ActionPlanSource(str, Enum):
    """Action plan source enumeration."""

    USER = "user"
    POLICY = "policy"
    INFRAMIND = "InfraMind"


class ActionPlan(BaseModel):
    """
    Action plan contains one or more decisions to be executed.

    Plans are validated by the policy engine before execution.
    """

    id: UUID
    decisions: list[Decision]
    source: ActionPlanSource
    correlation_id: Optional[str] = None
    created_at: datetime


class PolicyViolation(BaseModel):
    """
    Policy violation represents a rule that was not satisfied.
    """

    policy_id: UUID
    policy_name: str
    rule_type: PolicyRuleType
    message: str
    decision_verb: DecisionVerb
    decision_target: dict[str, str]
    action: str  # reject, warn, log


class PolicyEvaluationResult(BaseModel):
    """
    Result of evaluating an action plan against policies.
    """

    action_plan_id: UUID
    approved: bool
    violations: list[PolicyViolation] = Field(default_factory=list)
    evaluated_at: datetime
    mode: str  # enforce, dry_run, audit
    duration_ms: float

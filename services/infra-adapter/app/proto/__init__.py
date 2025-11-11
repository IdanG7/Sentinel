"""gRPC protocol definitions for Sentinel-InfraMind communication.

Note: This is a lightweight implementation for development.
For production, generate proper stubs using: make generate-proto
"""

from dataclasses import dataclass, field

__all__ = [
    "TelemetryPoint",
    "TelemetryBatch",
    "TelemetryRef",
    "Safety",
    "Decision",
    "ActionPlan",
    "ActionPlanRequest",
    "PlanAck",
    "Ack",
]


@dataclass
class TelemetryPoint:
    """Single telemetry metric observation."""

    name: str = ""
    value: float = 0.0
    labels: dict[str, str] = field(default_factory=dict)
    ts: int = 0  # Unix milliseconds


@dataclass
class TelemetryBatch:
    """Batch of telemetry points."""

    points: list[TelemetryPoint] = field(default_factory=list)
    cluster_id: str = ""
    batch_id: str = ""


@dataclass
class TelemetryRef:
    """Reference to a telemetry batch."""

    batch_id: str = ""
    cluster_id: str = ""


@dataclass
class Safety:
    """Safety constraints for action execution."""

    rate_limit: int = 0
    window: str = ""


@dataclass
class Decision:
    """Single action to be taken."""

    verb: str = ""  # scale, reschedule, rollback, etc.
    target: dict[str, str] = field(default_factory=dict)
    params: dict[str, str] = field(default_factory=dict)
    ttl: int = 0  # seconds
    safety: Safety | None = None


@dataclass
class ActionPlan:
    """Collection of decisions from InfraMind."""

    plan_id: str = ""
    decisions: list[Decision] = field(default_factory=list)
    source: str = ""
    created_at: int = 0
    correlation_id: str = ""


@dataclass
class ActionPlanRequest:
    """Request for streaming action plans."""

    cluster_id: str = ""
    filters: list[str] = field(default_factory=list)


@dataclass
class PlanAck:
    """Acknowledgment of plan execution."""

    plan_id: str = ""
    success: bool = False
    message: str = ""
    executed_at: int = 0
    metrics: dict[str, str] = field(default_factory=dict)


@dataclass
class Ack:
    """Generic acknowledgment."""

    success: bool = False
    message: str = ""

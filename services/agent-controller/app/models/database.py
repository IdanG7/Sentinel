"""Database models for Agent Controller."""

import uuid
from datetime import datetime
from enum import Enum

from sqlalchemy import JSON, Boolean, Column, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship

Base = declarative_base()


class AgentStatus(str, Enum):
    """Agent status enum."""

    ACTIVE = "active"
    PAUSED = "paused"
    FAILED = "failed"
    OFFLINE = "offline"


class TaskStatus(str, Enum):
    """Task status enum."""

    PENDING = "pending"
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    RATE_LIMITED = "rate_limited"


class AgentDB(Base):
    """Database model for agents."""

    __tablename__ = "agents"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(100), unique=True, nullable=False, index=True)
    version = Column(String(20), nullable=False)
    description = Column(String(500))

    # Agent metadata
    capabilities = Column(JSON, nullable=False, default=dict)
    configuration = Column(JSON, default=dict)

    # Status
    status = Column(String(20), nullable=False, default=AgentStatus.ACTIVE.value, index=True)
    health_score = Column(Float, default=1.0)
    last_heartbeat = Column(DateTime)

    # Statistics
    total_tasks = Column(Integer, default=0)
    successful_tasks = Column(Integer, default=0)
    failed_tasks = Column(Integer, default=0)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    tasks = relationship("AgentTaskDB", back_populates="agent", cascade="all, delete-orphan")


class AgentTaskDB(Base):
    """Database model for agent tasks."""

    __tablename__ = "agent_tasks"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    agent_id = Column(UUID(as_uuid=True), ForeignKey("agents.id"), nullable=False, index=True)

    # Task details
    task_type = Column(String(50), nullable=False, index=True)
    context = Column(JSON, nullable=False, default=dict)
    payload = Column(String)  # Large text/binary data

    # Status
    status = Column(String(20), nullable=False, default=TaskStatus.PENDING.value, index=True)
    progress = Column(Float, default=0.0)  # 0.0 to 1.0

    # Results
    result = Column(JSON)
    artifacts = Column(JSON, default=list)  # List of generated artifacts
    metrics = Column(JSON, default=dict)
    error_message = Column(String(1000))

    # Execution
    started_at = Column(DateTime, index=True)
    completed_at = Column(DateTime, index=True)
    duration_ms = Column(Integer)
    timeout_seconds = Column(Integer, default=600)

    # Retry logic
    retry_count = Column(Integer, default=0)
    max_retries = Column(Integer, default=3)

    # Correlation with InfraMind
    correlation_id = Column(UUID(as_uuid=True), index=True)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    agent = relationship("AgentDB", back_populates="tasks")
    fixes = relationship("FailureFixDB", back_populates="task", cascade="all, delete-orphan")


class FailureFixDB(Base):
    """Database model for failure fixes (PatchBot specific)."""

    __tablename__ = "failure_fixes"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    agent_task_id = Column(
        UUID(as_uuid=True), ForeignKey("agent_tasks.id"), nullable=False, index=True
    )

    # Failure details
    failure_signature = Column(String(255), nullable=False, index=True)
    repository = Column(String(255), nullable=False, index=True)
    branch = Column(String(100))
    failure_type = Column(String(50), nullable=False, index=True)

    # Fix details
    fix_pr_url = Column(String(500))
    fix_pr_number = Column(Integer)
    fix_confidence = Column(Float)
    fix_diff = Column(String)  # Git diff

    # Outcome
    fix_success = Column(Boolean, index=True)
    fix_merged = Column(Boolean, default=False)
    time_to_fix_seconds = Column(Integer)
    time_to_merge_seconds = Column(Integer)

    # CI/CD context
    build_url = Column(String(500))
    error_message = Column(String(1000))

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    task = relationship("AgentTaskDB", back_populates="fixes")


class RateLimitDB(Base):
    """Database model for rate limiting tracking."""

    __tablename__ = "rate_limits"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Scope
    agent_id = Column(UUID(as_uuid=True), index=True)
    repository = Column(String(255), index=True)
    scope = Column(String(50), nullable=False, index=True)  # agent, repo, global

    # Limits
    window_start = Column(DateTime, nullable=False, index=True)
    window_end = Column(DateTime, nullable=False, index=True)
    count = Column(Integer, default=0)
    limit = Column(Integer, nullable=False)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

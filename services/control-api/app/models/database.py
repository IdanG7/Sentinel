"""Database models for Sentinel Control API."""

from datetime import datetime
from uuid import uuid4

from sqlalchemy import JSON, Boolean, Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.core.database import Base


class User(Base):
    """User model for authentication."""

    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    username = Column(String(50), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)
    email = Column(String(255), unique=True, index=True)
    role = Column(String(50), nullable=False, default="operator")
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    def __repr__(self):
        return f"<User(username={self.username}, role={self.role})>"


class Cluster(Base):
    """Kubernetes cluster registry."""

    __tablename__ = "clusters"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    name = Column(String(255), unique=True, nullable=False, index=True)
    kubeconfig_path = Column(String(512))
    kubeconfig_data = Column(Text)  # Base64 encoded kubeconfig
    context = Column(String(255))
    namespace = Column(String(255), default="default", nullable=False)
    labels = Column(JSON, default=dict, nullable=False)
    gpu_families = Column(JSON, default=list, nullable=False)
    status = Column(String(50), default="active", nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    deployments = relationship("Deployment", back_populates="cluster", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Cluster(name={self.name}, status={self.status})>"


class Workload(Base):
    """Workload definition."""

    __tablename__ = "workloads"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    name = Column(String(255), nullable=False, index=True)
    type = Column(String(50), nullable=False)  # training, inference, batch
    image = Column(String(512), nullable=False)
    resources = Column(JSON, nullable=False)
    env = Column(JSON, default=dict)
    config_ref = Column(String(512))
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    deployments = relationship(
        "Deployment", back_populates="workload", cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<Workload(name={self.name}, type={self.type})>"


class Deployment(Base):
    """Deployment record."""

    __tablename__ = "deployments"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    workload_id = Column(UUID(as_uuid=True), ForeignKey("workloads.id"), nullable=False, index=True)
    cluster_id = Column(UUID(as_uuid=True), ForeignKey("clusters.id"), nullable=False, index=True)
    strategy = Column(String(50), default="rolling", nullable=False)
    replicas = Column(Integer, default=1, nullable=False)
    canary_config = Column(JSON)
    status = Column(String(50), default="pending", nullable=False, index=True)
    message = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    workload = relationship("Workload", back_populates="deployments")
    cluster = relationship("Cluster", back_populates="deployments")

    def __repr__(self):
        return f"<Deployment(id={self.id}, status={self.status})>"


class Policy(Base):
    """Policy definition."""

    __tablename__ = "policies"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    name = Column(String(255), nullable=False, index=True)
    rules = Column(JSON, nullable=False)
    priority = Column(Integer, default=0, nullable=False, index=True)
    enabled = Column(Boolean, default=True, nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    def __repr__(self):
        return f"<Policy(name={self.name}, priority={self.priority}, enabled={self.enabled})>"


class ActionPlan(Base):
    """Action plan record."""

    __tablename__ = "action_plans"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    decisions = Column(JSON, nullable=False)
    source = Column(String(50), nullable=False)  # user, policy, InfraMind
    correlation_id = Column(String(255), index=True)
    status = Column(String(50), default="pending", nullable=False, index=True)
    violations = Column(JSON)
    error = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    executed_at = Column(DateTime)

    def __repr__(self):
        return f"<ActionPlan(id={self.id}, status={self.status}, source={self.source})>"


class AuditLog(Base):
    """Audit log entries."""

    __tablename__ = "audit_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    actor = Column(String(255), nullable=False, index=True)
    verb = Column(String(50), nullable=False, index=True)
    target = Column(JSON, nullable=False)
    result = Column(String(50), nullable=False)
    reason = Column(Text)
    event_metadata = Column(JSON)

    def __repr__(self):
        return f"<AuditLog(actor={self.actor}, verb={self.verb}, result={self.result})>"

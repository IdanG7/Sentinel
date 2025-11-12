"""RBAC data models and database schemas."""

from datetime import datetime

from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Table
from sqlalchemy.orm import relationship

from .database import Base

# Association table for user-role assignments (many-to-many)
user_roles = Table(
    "user_roles",
    Base.metadata,
    Column("user_id", Integer, ForeignKey("users.id"), primary_key=True),
    Column("role_id", Integer, ForeignKey("roles.id"), primary_key=True),
)


class UserDB(Base):
    """Database model for users."""

    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True, nullable=False)
    email = Column(String, unique=True, index=True)
    hashed_password = Column(String, nullable=False)
    full_name = Column(String)
    tenant_id = Column(String, index=True)
    enabled = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    roles = relationship("RoleDB", secondary=user_roles, back_populates="users")
    api_keys = relationship("APIKeyDB", back_populates="user", cascade="all, delete-orphan")


class RoleDB(Base):
    """Database model for roles."""

    __tablename__ = "roles"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True, nullable=False)
    description = Column(String)
    permissions = Column(String)  # JSON array of permissions
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    users = relationship("UserDB", secondary=user_roles, back_populates="roles")


class APIKeyDB(Base):
    """Database model for API keys."""

    __tablename__ = "api_keys"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    key_hash = Column(String, unique=True, index=True, nullable=False)
    name = Column(String)
    expires_at = Column(DateTime)
    last_used_at = Column(DateTime)
    enabled = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    user = relationship("UserDB", back_populates="api_keys")


# Pydantic schemas for API


class UserCreate(BaseModel):
    """Schema for creating a user."""

    username: str = Field(..., min_length=3, max_length=50)
    email: EmailStr
    password: str = Field(..., min_length=8)
    full_name: str | None = None
    tenant_id: str | None = None
    roles: list[str] = ["viewer"]


class UserUpdate(BaseModel):
    """Schema for updating a user."""

    email: EmailStr | None = None
    full_name: str | None = None
    tenant_id: str | None = None
    enabled: bool | None = None
    roles: list[str] | None = None


class UserResponse(BaseModel):
    """Schema for user response."""

    id: int
    username: str
    email: str | None
    full_name: str | None
    tenant_id: str | None
    enabled: bool
    roles: list[str]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class RoleCreate(BaseModel):
    """Schema for creating a role."""

    name: str = Field(..., min_length=3, max_length=50)
    description: str | None = None
    permissions: list[str]


class RoleResponse(BaseModel):
    """Schema for role response."""

    id: int
    name: str
    description: str | None
    permissions: list[str]
    created_at: datetime

    class Config:
        from_attributes = True


class APIKeyCreate(BaseModel):
    """Schema for creating an API key."""

    name: str = Field(..., min_length=3, max_length=100)
    expires_days: int | None = Field(default=90, ge=1, le=365)


class APIKeyResponse(BaseModel):
    """Schema for API key response."""

    id: int
    name: str
    key: str  # Only returned on creation
    expires_at: datetime | None
    enabled: bool
    created_at: datetime

    class Config:
        from_attributes = True


class LoginRequest(BaseModel):
    """Schema for login request."""

    username: str
    password: str


class TokenResponse(BaseModel):
    """Schema for token response."""

    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserResponse

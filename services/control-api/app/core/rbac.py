"""RBAC (Role-Based Access Control) middleware and enforcement."""

import logging
from enum import Enum
from functools import wraps
from typing import Callable, Optional

from fastapi import HTTPException, Request, status
from pydantic import BaseModel

logger = logging.getLogger(__name__)


class Role(str, Enum):
    """User roles in Sentinel."""

    VIEWER = "viewer"
    OPERATOR = "operator"
    ADMIN = "admin"
    SYSTEM = "system"


class Permission(str, Enum):
    """Granular permissions for resources and actions."""

    # Workload permissions
    READ_WORKLOADS = "workloads:read"
    WRITE_WORKLOADS = "workloads:write"
    DELETE_WORKLOADS = "workloads:delete"

    # Deployment permissions
    READ_DEPLOYMENTS = "deployments:read"
    CREATE_DEPLOYMENTS = "deployments:create"
    SCALE_DEPLOYMENTS = "deployments:scale"
    ROLLBACK_DEPLOYMENTS = "deployments:rollback"
    DELETE_DEPLOYMENTS = "deployments:delete"

    # Action plan permissions
    READ_PLANS = "plans:read"
    EXECUTE_PLANS = "plans:execute"
    APPROVE_PLANS = "plans:approve"

    # Policy permissions
    READ_POLICIES = "policies:read"
    WRITE_POLICIES = "policies:write"
    DELETE_POLICIES = "policies:delete"

    # Cluster permissions
    READ_CLUSTERS = "clusters:read"
    MANAGE_CLUSTERS = "clusters:manage"

    # Audit permissions
    READ_AUDITS = "audits:read"

    # System permissions
    MANAGE_USERS = "users:manage"
    MANAGE_ROLES = "roles:manage"
    SYSTEM_ADMIN = "system:admin"


# Role to permissions mapping
ROLE_PERMISSIONS: dict[Role, list[Permission]] = {
    Role.VIEWER: [
        Permission.READ_WORKLOADS,
        Permission.READ_DEPLOYMENTS,
        Permission.READ_PLANS,
        Permission.READ_POLICIES,
        Permission.READ_CLUSTERS,
        Permission.READ_AUDITS,
    ],
    Role.OPERATOR: [
        Permission.READ_WORKLOADS,
        Permission.WRITE_WORKLOADS,
        Permission.READ_DEPLOYMENTS,
        Permission.CREATE_DEPLOYMENTS,
        Permission.SCALE_DEPLOYMENTS,
        Permission.ROLLBACK_DEPLOYMENTS,
        Permission.READ_PLANS,
        Permission.EXECUTE_PLANS,
        Permission.READ_POLICIES,
        Permission.READ_CLUSTERS,
        Permission.READ_AUDITS,
    ],
    Role.ADMIN: [
        # All permissions except system admin
        perm
        for perm in Permission
        if perm != Permission.SYSTEM_ADMIN
    ],
    Role.SYSTEM: [
        # All permissions (internal service-to-service)
        perm
        for perm in Permission
    ],
}


class User(BaseModel):
    """User model for RBAC."""

    id: str
    username: str
    email: Optional[str] = None
    role: Role
    tenant_id: Optional[str] = None
    enabled: bool = True


def get_current_user(request: Request) -> User:
    """
    Extract user from request.

    In production, this would decode JWT token and fetch user from database.
    For now, we extract from request.state (set by auth middleware).
    """
    if not hasattr(request.state, "user"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return request.state.user


def has_permission(user: User, permission: Permission) -> bool:
    """
    Check if user has a specific permission.

    Args:
        user: User to check
        permission: Permission to verify

    Returns:
        True if user has permission, False otherwise
    """
    if not user.enabled:
        return False

    user_permissions = ROLE_PERMISSIONS.get(user.role, [])
    return permission in user_permissions


def require_permission(permission: Permission):
    """
    Decorator to enforce permission on endpoint.

    Usage:
        @app.post("/api/v1/action-plans")
        @require_permission(Permission.EXECUTE_PLANS)
        async def create_action_plan(request: Request, plan: ActionPlan):
            # Only operators and admins can execute plans
            ...
    """

    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(request: Request, *args, **kwargs):
            user = get_current_user(request)

            if not has_permission(user, permission):
                logger.warning(
                    f"Permission denied: user={user.username} role={user.role} "
                    f"required={permission}"
                )
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Requires permission: {permission.value}",
                )

            logger.debug(
                f"Permission granted: user={user.username} role={user.role} "
                f"permission={permission}"
            )

            return await func(request, *args, **kwargs)

        return wrapper

    return decorator


def require_role(required_role: Role):
    """
    Decorator to enforce minimum role level on endpoint.

    Usage:
        @app.delete("/api/v1/workloads/{id}")
        @require_role(Role.ADMIN)
        async def delete_workload(request: Request, id: str):
            # Only admins can delete workloads
            ...
    """

    # Role hierarchy (higher number = more privileges)
    role_hierarchy = {
        Role.VIEWER: 1,
        Role.OPERATOR: 2,
        Role.ADMIN: 3,
        Role.SYSTEM: 4,
    }

    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(request: Request, *args, **kwargs):
            user = get_current_user(request)

            user_level = role_hierarchy.get(user.role, 0)
            required_level = role_hierarchy.get(required_role, 99)

            if user_level < required_level:
                logger.warning(
                    f"Insufficient role: user={user.username} role={user.role} "
                    f"required={required_role}"
                )
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Requires role: {required_role.value} or higher",
                )

            logger.debug(
                f"Role authorized: user={user.username} role={user.role} "
                f"required={required_role}"
            )

            return await func(request, *args, **kwargs)

        return wrapper

    return decorator


def check_tenant_access(user: User, resource_tenant_id: Optional[str]) -> bool:
    """
    Check if user can access a resource based on tenant isolation.

    Args:
        user: User making the request
        resource_tenant_id: Tenant ID of the resource

    Returns:
        True if user can access, False otherwise
    """
    # System role can access all tenants
    if user.role == Role.SYSTEM:
        return True

    # Admin can access all tenants
    if user.role == Role.ADMIN:
        return True

    # Users can only access their own tenant
    if user.tenant_id == resource_tenant_id:
        return True

    # Resources without tenant ID are accessible to all
    if resource_tenant_id is None:
        return True

    return False


def require_tenant_access(get_resource_tenant: Callable):
    """
    Decorator to enforce tenant isolation.

    Usage:
        @app.get("/api/v1/workloads/{id}")
        @require_tenant_access(lambda id: get_workload_tenant(id))
        async def get_workload(request: Request, id: str):
            # Users can only access workloads in their tenant
            ...
    """

    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(request: Request, *args, **kwargs):
            user = get_current_user(request)

            # Get tenant ID from resource
            resource_tenant_id = await get_resource_tenant(*args, **kwargs)

            if not check_tenant_access(user, resource_tenant_id):
                logger.warning(
                    f"Tenant access denied: user={user.username} "
                    f"user_tenant={user.tenant_id} resource_tenant={resource_tenant_id}"
                )
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Access denied: tenant mismatch",
                )

            return await func(request, *args, **kwargs)

        return wrapper

    return decorator


class RBACMiddleware:
    """
    FastAPI middleware to parse JWT and set user in request.state.

    In production, this would:
    1. Extract JWT from Authorization header
    2. Verify signature
    3. Decode payload
    4. Load user from database
    5. Set request.state.user
    """

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http":
            # TODO: Parse JWT from headers
            # For now, set a default user for development
            # In production: decode JWT, verify, load user from DB

            # Mock user for development
            from fastapi import Request

            request = Request(scope, receive)

            # Extract from header or use default
            auth_header = request.headers.get("authorization", "")

            if auth_header.startswith("Bearer "):
                token = auth_header[7:]
                # TODO: Decode JWT and load user
                # For now, parse role from token (dev only!)
                if "admin" in token:
                    scope["state"] = {
                        "user": User(
                            id="admin-1",
                            username="admin",
                            email="admin@example.com",
                            role=Role.ADMIN,
                        )
                    }
                elif "operator" in token:
                    scope["state"] = {
                        "user": User(
                            id="operator-1",
                            username="operator",
                            email="operator@example.com",
                            role=Role.OPERATOR,
                        )
                    }
                else:
                    scope["state"] = {
                        "user": User(
                            id="viewer-1",
                            username="viewer",
                            email="viewer@example.com",
                            role=Role.VIEWER,
                        )
                    }
            else:
                # No auth header - set viewer by default (dev only!)
                scope["state"] = {
                    "user": User(
                        id="anonymous",
                        username="anonymous",
                        role=Role.VIEWER,
                    )
                }

        await self.app(scope, receive, send)

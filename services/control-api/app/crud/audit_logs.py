"""CRUD operations for audit logs."""


from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.base import CRUDBase
from app.models.database import AuditLog


class AuditLogCreate(BaseModel):
    """Audit log creation schema."""

    actor: str
    verb: str
    target: dict
    result: str
    reason: str | None = None
    metadata: dict | None = None


class CRUDAuditLog(CRUDBase[AuditLog, AuditLogCreate, AuditLogCreate]):
    """CRUD operations for audit logs."""

    async def get_by_actor(
        self,
        db: AsyncSession,
        *,
        actor: str,
        skip: int = 0,
        limit: int = 100,
    ) -> list[AuditLog]:
        """
        Get audit logs by actor.

        Args:
            db: Database session
            actor: Actor name
            skip: Number of records to skip
            limit: Maximum number of records to return

        Returns:
            List of audit logs
        """
        result = await db.execute(
            select(AuditLog)
            .where(AuditLog.actor == actor)
            .order_by(AuditLog.timestamp.desc())
            .offset(skip)
            .limit(limit)
        )
        return list(result.scalars().all())


audit_log = CRUDAuditLog(AuditLog)

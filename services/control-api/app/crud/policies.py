"""CRUD operations for policies."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.base import CRUDBase
from app.models.database import Policy
from app.models.schemas import PolicyCreate


class CRUDPolicy(CRUDBase[Policy, PolicyCreate, PolicyCreate]):
    """CRUD operations for policies."""

    async def get_enabled(
        self,
        db: AsyncSession,
        *,
        skip: int = 0,
        limit: int = 100,
    ) -> list[Policy]:
        """
        Get enabled policies ordered by priority.

        Args:
            db: Database session
            skip: Number of records to skip
            limit: Maximum number of records to return

        Returns:
            List of enabled policies
        """
        result = await db.execute(
            select(Policy)
            .where(Policy.enabled)
            .order_by(Policy.priority.desc())
            .offset(skip)
            .limit(limit)
        )
        return list(result.scalars().all())


policy = CRUDPolicy(Policy)

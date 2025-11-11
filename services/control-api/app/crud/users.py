"""CRUD operations for users."""

from typing import Optional

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.base import CRUDBase
from app.models.database import User


class UserCreate(BaseModel):
    """User creation schema."""

    username: str
    hashed_password: str
    email: str | None = None
    role: str = "operator"


class CRUDUser(CRUDBase[User, UserCreate, UserCreate]):
    """CRUD operations for users."""

    async def get_by_username(
        self,
        db: AsyncSession,
        *,
        username: str,
    ) -> Optional[User]:
        """
        Get user by username.

        Args:
            db: Database session
            username: Username

        Returns:
            User or None
        """
        result = await db.execute(select(User).where(User.username == username))
        return result.scalar_one_or_none()


user = CRUDUser(User)

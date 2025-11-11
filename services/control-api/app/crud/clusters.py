"""CRUD operations for clusters."""

from typing import Optional

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.base import CRUDBase
from app.models.database import Cluster


class ClusterCreate(BaseModel):
    """Cluster creation schema."""

    name: str
    kubeconfig_path: str | None = None
    kubeconfig_data: str | None = None
    context: str | None = None
    namespace: str = "default"
    labels: dict = {}
    gpu_families: list = []


class CRUDCluster(CRUDBase[Cluster, ClusterCreate, ClusterCreate]):
    """CRUD operations for clusters."""

    async def get_by_name(
        self,
        db: AsyncSession,
        *,
        name: str,
    ) -> Optional[Cluster]:
        """
        Get cluster by name.

        Args:
            db: Database session
            name: Cluster name

        Returns:
            Cluster or None
        """
        result = await db.execute(select(Cluster).where(Cluster.name == name))
        return result.scalar_one_or_none()


cluster = CRUDCluster(Cluster)

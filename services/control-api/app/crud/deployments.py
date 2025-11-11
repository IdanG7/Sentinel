"""CRUD operations for deployments."""

from typing import List, Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.base import CRUDBase
from app.models.database import Deployment
from app.models.schemas import DeploymentCreate


class CRUDDeployment(CRUDBase[Deployment, DeploymentCreate, DeploymentCreate]):
    """CRUD operations for deployments."""

    async def get_by_status(
        self,
        db: AsyncSession,
        *,
        status: str,
        skip: int = 0,
        limit: int = 100,
    ) -> List[Deployment]:
        """
        Get deployments by status.

        Args:
            db: Database session
            status: Deployment status
            skip: Number of records to skip
            limit: Maximum number of records to return

        Returns:
            List of deployments
        """
        result = await db.execute(
            select(Deployment).where(Deployment.status == status).offset(skip).limit(limit)
        )
        return list(result.scalars().all())

    async def get_by_cluster(
        self,
        db: AsyncSession,
        *,
        cluster_id: UUID,
        skip: int = 0,
        limit: int = 100,
    ) -> List[Deployment]:
        """
        Get deployments by cluster.

        Args:
            db: Database session
            cluster_id: Cluster ID
            skip: Number of records to skip
            limit: Maximum number of records to return

        Returns:
            List of deployments
        """
        result = await db.execute(
            select(Deployment).where(Deployment.cluster_id == cluster_id).offset(skip).limit(limit)
        )
        return list(result.scalars().all())


deployment = CRUDDeployment(Deployment)

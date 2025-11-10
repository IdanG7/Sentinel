"""Workload management endpoints."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.core.security import get_current_user
from app.crud import workload as workload_crud
from app.models.schemas import WorkloadCreate, WorkloadResponse

router = APIRouter(prefix="/workloads", tags=["workloads"])


@router.post("", response_model=WorkloadResponse, status_code=status.HTTP_201_CREATED)
async def create_workload(
    workload: WorkloadCreate,
    db: AsyncSession = Depends(get_session),
    current_user: str = Depends(get_current_user),
) -> WorkloadResponse:
    """
    Register a new workload definition.

    Workloads define the container image, resources, and configuration
    for training, inference, or batch jobs.
    """
    # Create workload in database
    db_workload = await workload_crud.create(db, obj_in=workload)

    return WorkloadResponse(
        id=db_workload.id,
        name=db_workload.name,
        type=db_workload.type,
        image=db_workload.image,
        resources=db_workload.resources,
        env=db_workload.env,
        config_ref=db_workload.config_ref,
        created_at=db_workload.created_at,
        updated_at=db_workload.updated_at,
    )


@router.get("", response_model=list[WorkloadResponse])
async def list_workloads(
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_session),
    current_user: str = Depends(get_current_user),
) -> list[WorkloadResponse]:
    """
    List all registered workloads.
    """
    workloads = await workload_crud.get_multi(db, skip=skip, limit=limit)
    return [
        WorkloadResponse(
            id=w.id,
            name=w.name,
            type=w.type,
            image=w.image,
            resources=w.resources,
            env=w.env,
            config_ref=w.config_ref,
            created_at=w.created_at,
            updated_at=w.updated_at,
        )
        for w in workloads
    ]


@router.get("/{workload_id}", response_model=WorkloadResponse)
async def get_workload(
    workload_id: UUID,
    db: AsyncSession = Depends(get_session),
    current_user: str = Depends(get_current_user),
) -> WorkloadResponse:
    """
    Get a specific workload by ID.
    """
    workload = await workload_crud.get(db, workload_id)
    if not workload:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workload not found")

    return WorkloadResponse(
        id=workload.id,
        name=workload.name,
        type=workload.type,
        image=workload.image,
        resources=workload.resources,
        env=workload.env,
        config_ref=workload.config_ref,
        created_at=workload.created_at,
        updated_at=workload.updated_at,
    )


@router.delete("/{workload_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_workload(
    workload_id: UUID,
    db: AsyncSession = Depends(get_session),
    current_user: str = Depends(get_current_user),
) -> None:
    """
    Delete a workload.
    """
    workload = await workload_crud.delete(db, id=workload_id)
    if not workload:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workload not found")

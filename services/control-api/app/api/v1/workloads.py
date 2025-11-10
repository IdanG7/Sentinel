"""Workload management endpoints."""

from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, status

from app.core.security import get_current_user
from app.models.schemas import WorkloadCreate, WorkloadResponse

router = APIRouter(prefix="/workloads", tags=["workloads"])

# In-memory storage (replace with database)
workloads_db: dict[UUID, dict] = {}


@router.post("", response_model=WorkloadResponse, status_code=status.HTTP_201_CREATED)
async def create_workload(
    workload: WorkloadCreate,
    current_user: str = Depends(get_current_user),
) -> WorkloadResponse:
    """
    Register a new workload definition.

    Workloads define the container image, resources, and configuration
    for training, inference, or batch jobs.
    """
    from datetime import datetime

    workload_id = uuid4()
    now = datetime.utcnow()

    workload_data = {
        "id": workload_id,
        "name": workload.name,
        "type": workload.type.value,
        "image": workload.image,
        "resources": workload.resources.model_dump(),
        "env": workload.env,
        "config_ref": workload.config_ref,
        "created_at": now,
        "updated_at": now,
    }

    workloads_db[workload_id] = workload_data

    return WorkloadResponse(**workload_data)


@router.get("", response_model=list[WorkloadResponse])
async def list_workloads(
    current_user: str = Depends(get_current_user),
) -> list[WorkloadResponse]:
    """
    List all registered workloads.
    """
    return [WorkloadResponse(**w) for w in workloads_db.values()]


@router.get("/{workload_id}", response_model=WorkloadResponse)
async def get_workload(
    workload_id: UUID,
    current_user: str = Depends(get_current_user),
) -> WorkloadResponse:
    """
    Get a specific workload by ID.
    """
    workload = workloads_db.get(workload_id)
    if not workload:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workload not found")

    return WorkloadResponse(**workload)


@router.delete("/{workload_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_workload(
    workload_id: UUID,
    current_user: str = Depends(get_current_user),
) -> None:
    """
    Delete a workload.
    """
    if workload_id not in workloads_db:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workload not found")

    del workloads_db[workload_id]

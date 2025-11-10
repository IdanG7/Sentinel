"""Deployment management endpoints."""

from datetime import datetime
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, status

from app.core.security import get_current_user
from app.models.schemas import (
    DeploymentCreate,
    DeploymentResponse,
    DeploymentStatus,
    ScaleRequest,
)

router = APIRouter(prefix="/deployments", tags=["deployments"])

# In-memory storage (replace with database)
deployments_db: dict[UUID, dict] = {}


@router.post("", response_model=DeploymentResponse, status_code=status.HTTP_201_CREATED)
async def create_deployment(
    deployment: DeploymentCreate,
    current_user: str = Depends(get_current_user),
) -> DeploymentResponse:
    """
    Deploy a workload to a cluster.

    This initiates the deployment process. The actual deployment
    is handled asynchronously by the Pipeline Controller.
    """
    deployment_id = uuid4()
    now = datetime.utcnow()

    deployment_data = {
        "id": deployment_id,
        "workload_id": deployment.workload_id,
        "cluster_id": deployment.cluster_id,
        "strategy": deployment.strategy.value,
        "replicas": deployment.replicas,
        "canary_config": deployment.canary_config.model_dump() if deployment.canary_config else None,
        "status": DeploymentStatus.PENDING.value,
        "created_at": now,
        "updated_at": now,
    }

    deployments_db[deployment_id] = deployment_data

    # TODO: Send event to Kafka for Pipeline Controller

    return DeploymentResponse(**deployment_data)


@router.get("", response_model=list[DeploymentResponse])
async def list_deployments(
    current_user: str = Depends(get_current_user),
) -> list[DeploymentResponse]:
    """
    List all deployments.
    """
    return [DeploymentResponse(**d) for d in deployments_db.values()]


@router.get("/{deployment_id}", response_model=DeploymentResponse)
async def get_deployment(
    deployment_id: UUID,
    current_user: str = Depends(get_current_user),
) -> DeploymentResponse:
    """
    Get a specific deployment by ID.
    """
    deployment = deployments_db.get(deployment_id)
    if not deployment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Deployment not found")

    return DeploymentResponse(**deployment)


@router.post("/{deployment_id}/scale", response_model=DeploymentResponse)
async def scale_deployment(
    deployment_id: UUID,
    scale_request: ScaleRequest,
    current_user: str = Depends(get_current_user),
) -> DeploymentResponse:
    """
    Scale a deployment to the specified number of replicas.
    """
    deployment = deployments_db.get(deployment_id)
    if not deployment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Deployment not found")

    deployment["replicas"] = scale_request.replicas
    deployment["updated_at"] = datetime.utcnow()

    # TODO: Send scale event to Kafka for Pipeline Controller

    return DeploymentResponse(**deployment)


@router.post("/{deployment_id}/rollback", response_model=DeploymentResponse)
async def rollback_deployment(
    deployment_id: UUID,
    current_user: str = Depends(get_current_user),
) -> DeploymentResponse:
    """
    Rollback a deployment to the previous version.
    """
    deployment = deployments_db.get(deployment_id)
    if not deployment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Deployment not found")

    deployment["status"] = DeploymentStatus.ROLLED_BACK.value
    deployment["updated_at"] = datetime.utcnow()

    # TODO: Send rollback event to Kafka for Pipeline Controller

    return DeploymentResponse(**deployment)


@router.delete("/{deployment_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_deployment(
    deployment_id: UUID,
    current_user: str = Depends(get_current_user),
) -> None:
    """
    Delete a deployment.
    """
    if deployment_id not in deployments_db:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Deployment not found")

    # TODO: Send delete event to Kafka to cleanup cluster resources

    del deployments_db[deployment_id]

"""Deployment management endpoints."""

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.core.events import get_event_publisher
from app.core.security import get_current_user
from app.crud import deployment as deployment_crud
from app.models.schemas import (
    DeploymentCreate,
    DeploymentResponse,
    DeploymentStatus,
    ScaleRequest,
)

router = APIRouter(prefix="/deployments", tags=["deployments"])


@router.post("", response_model=DeploymentResponse, status_code=status.HTTP_201_CREATED)
async def create_deployment(
    deployment: DeploymentCreate,
    db: AsyncSession = Depends(get_session),
    current_user: str = Depends(get_current_user),
) -> DeploymentResponse:
    """
    Deploy a workload to a cluster.

    This initiates the deployment process. The actual deployment
    is handled asynchronously by the Pipeline Controller.
    """
    # Create deployment in database
    db_deployment = await deployment_crud.create(db, obj_in=deployment)

    # Prepare deployment data for events
    deployment_data = {
        "id": db_deployment.id,
        "workload_id": db_deployment.workload_id,
        "cluster_id": db_deployment.cluster_id,
        "strategy": db_deployment.strategy,
        "replicas": db_deployment.replicas,
        "canary_config": db_deployment.canary_config,
        "status": db_deployment.status,
        "created_at": db_deployment.created_at,
        "updated_at": db_deployment.updated_at,
    }

    # Publish events to Kafka
    event_publisher = get_event_publisher()
    await event_publisher.publish_deployment_event(
        deployment_id=db_deployment.id,
        event_type="deployment.created",
        data=deployment_data,
    )
    await event_publisher.publish_audit_event(
        actor=current_user,
        verb="create",
        target={"type": "deployment", "id": str(db_deployment.id)},
        result="success",
        metadata={
            "workload_id": str(deployment.workload_id),
            "cluster_id": str(deployment.cluster_id),
        },
    )

    return DeploymentResponse(
        id=db_deployment.id,
        workload_id=db_deployment.workload_id,
        cluster_id=db_deployment.cluster_id,
        strategy=db_deployment.strategy,
        replicas=db_deployment.replicas,
        canary_config=db_deployment.canary_config,
        status=db_deployment.status,
        created_at=db_deployment.created_at,
        updated_at=db_deployment.updated_at,
    )


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

    old_replicas = deployment["replicas"]
    deployment["replicas"] = scale_request.replicas
    deployment["status"] = DeploymentStatus.DEPLOYING.value
    deployment["updated_at"] = datetime.utcnow()

    # Publish events to Kafka
    event_publisher = get_event_publisher()
    await event_publisher.publish_deployment_event(
        deployment_id=deployment_id,
        event_type="deployment.scaled",
        data={
            "deployment_id": deployment_id,
            "old_replicas": old_replicas,
            "new_replicas": scale_request.replicas,
        },
    )
    await event_publisher.publish_audit_event(
        actor=current_user,
        verb="scale",
        target={"type": "deployment", "id": str(deployment_id)},
        result="success",
        metadata={"old_replicas": old_replicas, "new_replicas": scale_request.replicas},
    )

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

    # Publish events to Kafka
    event_publisher = get_event_publisher()
    await event_publisher.publish_deployment_event(
        deployment_id=deployment_id,
        event_type="deployment.rollback",
        data={"deployment_id": deployment_id},
    )
    await event_publisher.publish_audit_event(
        actor=current_user,
        verb="rollback",
        target={"type": "deployment", "id": str(deployment_id)},
        result="success",
    )

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

    # Publish events to Kafka to cleanup cluster resources
    event_publisher = get_event_publisher()
    await event_publisher.publish_deployment_event(
        deployment_id=deployment_id,
        event_type="deployment.deleted",
        data={"deployment_id": deployment_id},
    )
    await event_publisher.publish_audit_event(
        actor=current_user,
        verb="delete",
        target={"type": "deployment", "id": str(deployment_id)},
        result="success",
    )

    del deployments_db[deployment_id]

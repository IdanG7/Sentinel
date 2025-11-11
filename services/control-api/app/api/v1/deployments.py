"""Deployment management endpoints."""

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
        deployment_id=db_deployment.id,  # type: ignore[arg-type]
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
    db: AsyncSession = Depends(get_session),
    current_user: str = Depends(get_current_user),
) -> list[DeploymentResponse]:
    """
    List all deployments.
    """
    deployments = await deployment_crud.get_multi(db)
    return [
        DeploymentResponse(
            id=d.id,
            workload_id=d.workload_id,
            cluster_id=d.cluster_id,
            strategy=d.strategy,
            replicas=d.replicas,
            canary_config=d.canary_config,
            status=d.status,
            created_at=d.created_at,
            updated_at=d.updated_at,
        )
        for d in deployments
    ]


@router.get("/{deployment_id}", response_model=DeploymentResponse)
async def get_deployment(
    deployment_id: UUID,
    db: AsyncSession = Depends(get_session),
    current_user: str = Depends(get_current_user),
) -> DeploymentResponse:
    """
    Get a specific deployment by ID.
    """
    deployment = await deployment_crud.get(db, id=deployment_id)
    if not deployment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Deployment not found"
        )

    return DeploymentResponse(
        id=deployment.id,
        workload_id=deployment.workload_id,
        cluster_id=deployment.cluster_id,
        strategy=deployment.strategy,
        replicas=deployment.replicas,
        canary_config=deployment.canary_config,
        status=deployment.status,
        created_at=deployment.created_at,
        updated_at=deployment.updated_at,
    )


@router.post("/{deployment_id}/scale", response_model=DeploymentResponse)
async def scale_deployment(
    deployment_id: UUID,
    scale_request: ScaleRequest,
    db: AsyncSession = Depends(get_session),
    current_user: str = Depends(get_current_user),
) -> DeploymentResponse:
    """
    Scale a deployment to the specified number of replicas.
    """
    deployment = await deployment_crud.get(db, id=deployment_id)
    if not deployment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Deployment not found"
        )

    old_replicas = deployment.replicas

    # Update deployment with new replica count
    updated_deployment = await deployment_crud.update(
        db,
        db_obj=deployment,
        obj_in={
            "replicas": scale_request.replicas,
            "status": DeploymentStatus.DEPLOYING.value,
        },
    )

    # Publish events to Kafka
    event_publisher = get_event_publisher()
    await event_publisher.publish_deployment_event(
        deployment_id=deployment_id,
        event_type="deployment.scaled",
        data={
            "deployment_id": str(deployment_id),
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

    return DeploymentResponse(
        id=updated_deployment.id,
        workload_id=updated_deployment.workload_id,
        cluster_id=updated_deployment.cluster_id,
        strategy=updated_deployment.strategy,
        replicas=updated_deployment.replicas,
        canary_config=updated_deployment.canary_config,
        status=updated_deployment.status,
        created_at=updated_deployment.created_at,
        updated_at=updated_deployment.updated_at,
    )


@router.post("/{deployment_id}/rollback", response_model=DeploymentResponse)
async def rollback_deployment(
    deployment_id: UUID,
    db: AsyncSession = Depends(get_session),
    current_user: str = Depends(get_current_user),
) -> DeploymentResponse:
    """
    Rollback a deployment to the previous version.
    """
    deployment = await deployment_crud.get(db, id=deployment_id)
    if not deployment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Deployment not found"
        )

    # Update deployment status to rolled back
    updated_deployment = await deployment_crud.update(
        db,
        db_obj=deployment,
        obj_in={"status": DeploymentStatus.ROLLED_BACK.value},
    )

    # Publish events to Kafka
    event_publisher = get_event_publisher()
    await event_publisher.publish_deployment_event(
        deployment_id=deployment_id,
        event_type="deployment.rollback",
        data={"deployment_id": str(deployment_id)},
    )
    await event_publisher.publish_audit_event(
        actor=current_user,
        verb="rollback",
        target={"type": "deployment", "id": str(deployment_id)},
        result="success",
    )

    return DeploymentResponse(
        id=updated_deployment.id,
        workload_id=updated_deployment.workload_id,
        cluster_id=updated_deployment.cluster_id,
        strategy=updated_deployment.strategy,
        replicas=updated_deployment.replicas,
        canary_config=updated_deployment.canary_config,
        status=updated_deployment.status,
        created_at=updated_deployment.created_at,
        updated_at=updated_deployment.updated_at,
    )


@router.delete("/{deployment_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_deployment(
    deployment_id: UUID,
    db: AsyncSession = Depends(get_session),
    current_user: str = Depends(get_current_user),
) -> None:
    """
    Delete a deployment.
    """
    deployment = await deployment_crud.get(db, id=deployment_id)
    if not deployment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Deployment not found"
        )

    # Publish events to Kafka to cleanup cluster resources
    event_publisher = get_event_publisher()
    await event_publisher.publish_deployment_event(
        deployment_id=deployment_id,
        event_type="deployment.deleted",
        data={"deployment_id": str(deployment_id)},
    )
    await event_publisher.publish_audit_event(
        actor=current_user,
        verb="delete",
        target={"type": "deployment", "id": str(deployment_id)},
        result="success",
    )

    # Delete deployment from database
    await deployment_crud.delete(db, id=deployment_id)

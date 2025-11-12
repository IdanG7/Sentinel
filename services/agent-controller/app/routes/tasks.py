"""Task management API endpoints."""

import logging
from typing import List, Optional
from uuid import UUID

import redis.asyncio as redis
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import get_settings
from ..database import get_db
from ..models import AgentTaskCreate, AgentTaskResponse, AgentTaskUpdate
from ..services import TaskManager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/tasks", tags=["tasks"])

settings = get_settings()


# Dependency to get Redis client
async def get_redis() -> redis.Redis:
    """Get Redis client."""
    client = redis.from_url(settings.redis_url, decode_responses=False)
    try:
        yield client
    finally:
        await client.close()


@router.post("/", response_model=AgentTaskResponse, status_code=status.HTTP_201_CREATED)
async def create_task(
    task_data: AgentTaskCreate,
    db: AsyncSession = Depends(get_db),
    redis_client: redis.Redis = Depends(get_redis),
):
    """
    Create a new task.

    The task will be automatically assigned to a capable agent based on:
    - Task type capabilities
    - Agent health score
    - Current agent capacity

    The task will be queued and executed asynchronously.
    """
    manager = TaskManager(db, redis_client)

    task = await manager.create_task(
        task_type=task_data.task_type,
        context=task_data.context,
        payload=task_data.payload,
        timeout_seconds=task_data.timeout_seconds,
        correlation_id=task_data.correlation_id,
    )

    if not task:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="No capable agents available for this task",
        )

    # Convert to response model
    response = AgentTaskResponse.model_validate(task)
    response.agent_name = (await manager.agent_registry.get_agent(task.agent_id)).name

    return response


@router.get("/", response_model=List[AgentTaskResponse])
async def list_tasks(
    agent_id: Optional[UUID] = None,
    status: Optional[str] = None,
    task_type: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
    redis_client: redis.Redis = Depends(get_redis),
):
    """
    List tasks with filters.

    Filters:
    - agent_id: Filter by agent
    - status: Filter by status (pending, queued, running, completed, failed, cancelled)
    - task_type: Filter by task type
    - limit: Maximum results (default: 100)
    - offset: Result offset (default: 0)
    """
    manager = TaskManager(db, redis_client)

    tasks = await manager.list_tasks(
        agent_id=agent_id,
        status=status,
        task_type=task_type,
        limit=limit,
        offset=offset,
    )

    # Convert to response models with agent names
    responses = []
    for task in tasks:
        response = AgentTaskResponse.model_validate(task)
        agent = await manager.agent_registry.get_agent(task.agent_id)
        response.agent_name = agent.name if agent else "unknown"
        responses.append(response)

    return responses


@router.get("/{task_id}", response_model=AgentTaskResponse)
async def get_task(
    task_id: UUID,
    db: AsyncSession = Depends(get_db),
    redis_client: redis.Redis = Depends(get_redis),
):
    """Get task details by ID."""
    manager = TaskManager(db, redis_client)
    task = await manager.get_task(task_id)

    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Task {task_id} not found",
        )

    # Convert to response
    response = AgentTaskResponse.model_validate(task)
    agent = await manager.agent_registry.get_agent(task.agent_id)
    response.agent_name = agent.name if agent else "unknown"

    return response


@router.patch("/{task_id}", response_model=AgentTaskResponse)
async def update_task(
    task_id: UUID,
    update_data: AgentTaskUpdate,
    db: AsyncSession = Depends(get_db),
    redis_client: redis.Redis = Depends(get_redis),
):
    """
    Update task (typically called by agents).

    Can update:
    - status
    - progress (0.0 - 1.0)
    - result
    - artifacts
    - metrics
    - error_message
    """
    manager = TaskManager(db, redis_client)

    # Update progress if provided
    if update_data.progress is not None:
        await manager.update_task_progress(
            task_id,
            update_data.progress,
            update_data.metrics,
        )

    # Complete task if status indicates completion
    if update_data.status in ["completed", "failed"]:
        success = update_data.status == "completed"
        await manager.complete_task(
            task_id,
            success=success,
            result=update_data.result,
            error_message=update_data.error_message,
        )

    # Get updated task
    task = await manager.get_task(task_id)

    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Task {task_id} not found",
        )

    response = AgentTaskResponse.model_validate(task)
    agent = await manager.agent_registry.get_agent(task.agent_id)
    response.agent_name = agent.name if agent else "unknown"

    return response


@router.post("/{task_id}/cancel", status_code=status.HTTP_204_NO_CONTENT)
async def cancel_task(
    task_id: UUID,
    db: AsyncSession = Depends(get_db),
    redis_client: redis.Redis = Depends(get_redis),
):
    """
    Cancel a queued or running task.

    This will remove the task from the queue and mark it as cancelled.
    """
    manager = TaskManager(db, redis_client)
    cancelled = await manager.cancel_task(task_id)

    if not cancelled:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Task {task_id} not found or cannot be cancelled",
        )


@router.post("/{task_id}/retry", response_model=AgentTaskResponse)
async def retry_task(
    task_id: UUID,
    db: AsyncSession = Depends(get_db),
    redis_client: redis.Redis = Depends(get_redis),
):
    """
    Manually retry a failed task.

    The task will be requeued with incremented retry count.
    """
    manager = TaskManager(db, redis_client)

    retried = await manager.task_queue.retry_task(task_id)

    if not retried:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Task cannot be retried (not found or max retries exceeded)",
        )

    task = await manager.get_task(task_id)
    response = AgentTaskResponse.model_validate(task)
    agent = await manager.agent_registry.get_agent(task.agent_id)
    response.agent_name = agent.name if agent else "unknown"

    return response


@router.post("/{task_id}/reassign")
async def reassign_task(
    task_id: UUID,
    new_agent_id: Optional[UUID] = None,
    db: AsyncSession = Depends(get_db),
    redis_client: redis.Redis = Depends(get_redis),
):
    """
    Reassign a task to a different agent.

    If new_agent_id is not provided, the system will find the best available agent.
    """
    manager = TaskManager(db, redis_client)

    reassigned = await manager.reassign_task(task_id, new_agent_id)

    if not reassigned:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Task cannot be reassigned",
        )

    task = await manager.get_task(task_id)
    response = AgentTaskResponse.model_validate(task)
    agent = await manager.agent_registry.get_agent(task.agent_id)
    response.agent_name = agent.name if agent else "unknown"

    return response


@router.get("/correlation/{correlation_id}", response_model=List[AgentTaskResponse])
async def get_tasks_by_correlation(
    correlation_id: UUID,
    db: AsyncSession = Depends(get_db),
    redis_client: redis.Redis = Depends(get_redis),
):
    """
    Get all tasks linked to an InfraMind prediction.

    This allows tracking which agent tasks were triggered by a specific
    InfraMind failure prediction.
    """
    manager = TaskManager(db, redis_client)

    tasks = await manager.get_tasks_by_correlation(correlation_id)

    responses = []
    for task in tasks:
        response = AgentTaskResponse.model_validate(task)
        agent = await manager.agent_registry.get_agent(task.agent_id)
        response.agent_name = agent.name if agent else "unknown"
        responses.append(response)

    return responses


@router.get("/statistics/summary")
async def get_task_statistics(
    agent_id: Optional[UUID] = None,
    db: AsyncSession = Depends(get_db),
    redis_client: redis.Redis = Depends(get_redis),
):
    """
    Get task execution statistics.

    Returns:
    - Total tasks
    - Tasks by status
    - Average duration
    - Success rate

    Optional filter by agent_id.
    """
    manager = TaskManager(db, redis_client)
    stats = await manager.get_task_statistics(agent_id=agent_id)
    return stats


@router.get("/agent/{agent_id}/queue")
async def get_agent_queue_status(
    agent_id: UUID,
    db: AsyncSession = Depends(get_db),
    redis_client: redis.Redis = Depends(get_redis),
):
    """
    Get queue status for a specific agent.

    Returns:
    - Queue depth per priority
    - Active task count
    - List of active task IDs
    """
    manager = TaskManager(db, redis_client)
    status = await manager.get_agent_queue_status(agent_id)
    return status

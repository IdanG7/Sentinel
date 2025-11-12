"""Agent management API endpoints."""

import logging
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..models import AgentCreate, AgentHeartbeat, AgentResponse, AgentUpdate
from ..services import AgentRegistry

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/agents", tags=["agents"])


@router.post("/", response_model=AgentResponse, status_code=status.HTTP_201_CREATED)
async def register_agent(
    agent_data: AgentCreate,
    db: AsyncSession = Depends(get_db),
):
    """
    Register a new agent.

    The agent must provide:
    - Unique name
    - Version
    - Capabilities (supported tasks, max concurrent tasks)
    - Optional configuration
    """
    registry = AgentRegistry(db)

    try:
        agent = await registry.register_agent(agent_data)
        return agent
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e),
        )


@router.get("/", response_model=List[AgentResponse])
async def list_agents(
    status: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
):
    """
    List all registered agents.

    Filters:
    - status: Filter by agent status (active, paused, failed, offline)
    - limit: Maximum number of results (default: 100)
    - offset: Number of results to skip (default: 0)
    """
    registry = AgentRegistry(db)
    agents = await registry.list_agents(status=status, limit=limit, offset=offset)
    return agents


@router.get("/{agent_id}", response_model=AgentResponse)
async def get_agent(
    agent_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Get agent details by ID."""
    registry = AgentRegistry(db)
    agent = await registry.get_agent(agent_id)

    if not agent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Agent {agent_id} not found",
        )

    return agent


@router.get("/name/{name}", response_model=AgentResponse)
async def get_agent_by_name(
    name: str,
    db: AsyncSession = Depends(get_db),
):
    """Get agent details by name."""
    registry = AgentRegistry(db)
    agent = await registry.get_agent_by_name(name)

    if not agent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Agent '{name}' not found",
        )

    return agent


@router.patch("/{agent_id}", response_model=AgentResponse)
async def update_agent(
    agent_id: UUID,
    update_data: AgentUpdate,
    db: AsyncSession = Depends(get_db),
):
    """
    Update agent configuration.

    Can update:
    - version
    - description
    - capabilities
    - configuration
    - status (active, paused, offline)
    """
    registry = AgentRegistry(db)
    agent = await registry.update_agent(agent_id, update_data)

    if not agent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Agent {agent_id} not found",
        )

    return agent


@router.delete("/{agent_id}", status_code=status.HTTP_204_NO_CONTENT)
async def unregister_agent(
    agent_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """
    Unregister an agent.

    This will delete the agent and all its associated tasks.
    """
    registry = AgentRegistry(db)
    deleted = await registry.delete_agent(agent_id)

    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Agent {agent_id} not found",
        )


@router.post("/{agent_id}/heartbeat", status_code=status.HTTP_204_NO_CONTENT)
async def update_heartbeat(
    agent_id: UUID,
    heartbeat: AgentHeartbeat,
    db: AsyncSession = Depends(get_db),
):
    """
    Update agent heartbeat.

    Agents should send heartbeats every 30-60 seconds with:
    - health_score: Current health (0.0-1.0)
    - active_tasks: Number of currently running tasks
    - metrics: Optional performance metrics
    """
    registry = AgentRegistry(db)
    updated = await registry.update_heartbeat(
        agent_id,
        heartbeat.health_score,
        heartbeat.metrics,
    )

    if not updated:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Agent {agent_id} not found",
        )


@router.get("/statistics/summary")
async def get_agent_statistics(
    db: AsyncSession = Depends(get_db),
):
    """
    Get agent statistics.

    Returns counts by status:
    - total
    - active
    - paused
    - failed
    - offline
    """
    registry = AgentRegistry(db)
    stats = await registry.get_agent_statistics()
    return stats


@router.get("/discover/{task_type}", response_model=List[AgentResponse])
async def discover_capable_agents(
    task_type: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Discover agents capable of handling a specific task type.

    Returns active agents that support the requested task type.
    """
    registry = AgentRegistry(db)
    agents = await registry.find_capable_agents(task_type)
    return agents

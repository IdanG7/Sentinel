"""Action plan management endpoints."""

from datetime import datetime
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, status

from app.core.security import get_current_user
from app.models.schemas import (
    ActionPlanCreate,
    ActionPlanResponse,
    ActionPlanStatus,
)

router = APIRouter(prefix="/action-plans", tags=["action-plans"])

# In-memory storage (replace with database)
action_plans_db: dict[UUID, dict] = {}


@router.post("", response_model=ActionPlanResponse, status_code=status.HTTP_201_CREATED)
async def create_action_plan(
    action_plan: ActionPlanCreate,
    current_user: str = Depends(get_current_user),
) -> ActionPlanResponse:
    """
    Submit an action plan for execution.

    Action plans contain one or more decisions (actions) to be applied
    to the infrastructure. Plans are validated against policies before execution.
    """
    plan_id = uuid4()
    now = datetime.utcnow()

    plan_data = {
        "id": plan_id,
        "decisions": [decision.model_dump() for decision in action_plan.decisions],
        "source": action_plan.source.value,
        "correlation_id": action_plan.correlation_id,
        "status": ActionPlanStatus.PENDING.value,
        "created_at": now,
        "executed_at": None,
    }

    action_plans_db[plan_id] = plan_data

    # TODO: Send plan to Policy Engine for validation
    # TODO: If approved, send to Pipeline Controller for execution

    return ActionPlanResponse(**plan_data)


@router.get("", response_model=list[ActionPlanResponse])
async def list_action_plans(
    current_user: str = Depends(get_current_user),
    limit: int = 100,
) -> list[ActionPlanResponse]:
    """
    List action plans.
    """
    plans = list(action_plans_db.values())
    # Sort by created_at descending
    plans.sort(key=lambda x: x["created_at"], reverse=True)
    return [ActionPlanResponse(**p) for p in plans[:limit]]


@router.get("/{plan_id}", response_model=ActionPlanResponse)
async def get_action_plan(
    plan_id: UUID,
    current_user: str = Depends(get_current_user),
) -> ActionPlanResponse:
    """
    Get a specific action plan by ID.
    """
    plan = action_plans_db.get(plan_id)
    if not plan:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Action plan not found")

    return ActionPlanResponse(**plan)

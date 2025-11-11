"""Action plan management endpoints."""

import logging
from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status

from app.core.events import get_event_publisher
from app.core.security import get_current_user
from app.models.schemas import (
    ActionPlanCreate,
    ActionPlanResponse,
    ActionPlanStatus,
)
from app.services.plan_executor import PlanExecutor

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/action-plans", tags=["action-plans"])

# In-memory storage (replace with database)
action_plans_db: dict[UUID, dict] = {}

# Initialize plan executor (singleton)
_plan_executor: PlanExecutor | None = None


def get_plan_executor() -> PlanExecutor:
    """Get or create plan executor instance."""
    global _plan_executor
    if _plan_executor is None:
        event_publisher = get_event_publisher()
        _plan_executor = PlanExecutor(event_publisher=event_publisher)
    return _plan_executor


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
        "status": ActionPlanStatus.VALIDATING.value,
        "created_at": now,
        "executed_at": None,
    }

    action_plans_db[plan_id] = plan_data

    # Publish events to Kafka for Policy Engine validation
    event_publisher = get_event_publisher()
    await event_publisher.publish_action_plan_event(
        plan_id=plan_id,
        event_type="action_plan.created",
        data=plan_data,
    )
    await event_publisher.publish_audit_event(
        actor=current_user,
        verb="submit",
        target={"type": "action_plan", "id": str(plan_id)},
        result="success",
        metadata={
            "source": action_plan.source.value,
            "decisions_count": len(action_plan.decisions),
        },
    )

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
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Action plan not found"
        )

    return ActionPlanResponse(**plan)


@router.post("/{plan_id}/execute", response_model=dict[str, Any])
async def execute_action_plan(
    plan_id: UUID,
    background_tasks: BackgroundTasks,
    shadow_mode: bool = False,
    current_user: str = Depends(get_current_user),
    executor: PlanExecutor = Depends(get_plan_executor),
) -> dict[str, Any]:
    """
    Execute an action plan.

    This endpoint triggers execution of a validated action plan.
    Execution happens in the background and can be monitored via status endpoint.

    Args:
        plan_id: Action plan ID to execute
        shadow_mode: If True, simulate execution without actually applying changes
    """
    plan = action_plans_db.get(plan_id)
    if not plan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Action plan not found"
        )

    # Check if already executing or completed
    if plan["status"] in [
        ActionPlanStatus.EXECUTING.value,
        ActionPlanStatus.COMPLETED.value,
    ]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Plan is already {plan['status']}",
        )

    # Update status to executing
    plan["status"] = ActionPlanStatus.EXECUTING.value
    action_plans_db[plan_id] = plan

    # Execute plan in background
    async def execute_plan() -> None:
        try:
            result = await executor.execute_plan(
                plan_id, plan, actor=current_user, shadow_mode=shadow_mode
            )

            # Update plan status on completion
            plan["status"] = ActionPlanStatus.COMPLETED.value
            plan["executed_at"] = result["executed_at"]
            action_plans_db[plan_id] = plan

        except Exception as e:
            # Update plan status on failure
            logger.error(f"Failed to execute plan {plan_id}: {e}", exc_info=True)
            plan["status"] = ActionPlanStatus.FAILED.value
            action_plans_db[plan_id] = plan

    background_tasks.add_task(execute_plan)

    mode_str = "shadow" if shadow_mode else "live"
    return {
        "plan_id": str(plan_id),
        "status": "executing",
        "mode": mode_str,
        "message": f"Plan execution started in background ({mode_str} mode)",
    }


@router.get("/{plan_id}/status", response_model=dict[str, Any])
async def get_execution_status(
    plan_id: UUID,
    current_user: str = Depends(get_current_user),
    executor: PlanExecutor = Depends(get_plan_executor),
) -> dict[str, Any]:
    """
    Get execution status for an action plan.

    Returns detailed execution metrics and results.
    """
    plan = action_plans_db.get(plan_id)
    if not plan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Action plan not found"
        )

    # Get execution details from executor
    execution_status = executor.get_execution_status(plan_id)

    return {
        "plan_id": str(plan_id),
        "status": plan["status"],
        "created_at": plan["created_at"],
        "executed_at": plan.get("executed_at"),
        "execution_details": execution_status,
    }

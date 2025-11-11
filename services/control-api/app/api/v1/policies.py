"""Policy management endpoints."""

from datetime import datetime
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, status

from app.core.security import get_current_user
from app.models.schemas import PolicyCreate, PolicyResponse

router = APIRouter(prefix="/policies", tags=["policies"])

# In-memory storage (replace with database)
policies_db: dict[UUID, dict] = {}


@router.post("", response_model=PolicyResponse, status_code=status.HTTP_201_CREATED)
async def create_policy(
    policy: PolicyCreate,
    current_user: str = Depends(get_current_user),
) -> PolicyResponse:
    """
    Create a new policy set.

    Policies define constraints and rules that all actions must satisfy.
    """
    policy_id = uuid4()
    now = datetime.utcnow()

    policy_data = {
        "id": policy_id,
        "name": policy.name,
        "rules": [rule.model_dump() for rule in policy.rules],
        "priority": policy.priority,
        "enabled": policy.enabled,
        "created_at": now,
        "updated_at": now,
    }

    policies_db[policy_id] = policy_data

    return PolicyResponse(**policy_data)


@router.get("", response_model=list[PolicyResponse])
async def list_policies(
    current_user: str = Depends(get_current_user),
) -> list[PolicyResponse]:
    """
    List all policies.
    """
    return [PolicyResponse(**p) for p in policies_db.values()]


@router.get("/{policy_id}", response_model=PolicyResponse)
async def get_policy(
    policy_id: UUID,
    current_user: str = Depends(get_current_user),
) -> PolicyResponse:
    """
    Get a specific policy by ID.
    """
    policy = policies_db.get(policy_id)
    if not policy:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Policy not found"
        )

    return PolicyResponse(**policy)


@router.put("/{policy_id}", response_model=PolicyResponse)
async def update_policy(
    policy_id: UUID,
    policy: PolicyCreate,
    current_user: str = Depends(get_current_user),
) -> PolicyResponse:
    """
    Update an existing policy.
    """
    if policy_id not in policies_db:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Policy not found"
        )

    policy_data = policies_db[policy_id]
    policy_data.update(
        {
            "name": policy.name,
            "rules": [rule.model_dump() for rule in policy.rules],
            "priority": policy.priority,
            "enabled": policy.enabled,
            "updated_at": datetime.utcnow(),
        }
    )

    return PolicyResponse(**policy_data)


@router.delete("/{policy_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_policy(
    policy_id: UUID,
    current_user: str = Depends(get_current_user),
) -> None:
    """
    Delete a policy.
    """
    if policy_id not in policies_db:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Policy not found"
        )

    del policies_db[policy_id]

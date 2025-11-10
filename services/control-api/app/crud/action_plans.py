"""CRUD operations for action plans."""

from app.crud.base import CRUDBase
from app.models.database import ActionPlan
from app.models.schemas import ActionPlanCreate


class CRUDActionPlan(CRUDBase[ActionPlan, ActionPlanCreate, ActionPlanCreate]):
    """CRUD operations for action plans."""

    pass


action_plan = CRUDActionPlan(ActionPlan)

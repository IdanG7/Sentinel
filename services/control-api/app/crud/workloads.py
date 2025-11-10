"""CRUD operations for workloads."""

from app.crud.base import CRUDBase
from app.models.database import Workload
from app.models.schemas import WorkloadCreate


class CRUDWorkload(CRUDBase[Workload, WorkloadCreate, WorkloadCreate]):
    """CRUD operations for workloads."""

    pass


workload = CRUDWorkload(Workload)

import uuid

from vmss_api.core.schemas import CamelModel


class BranchRollupOut(CamelModel):
    branch_id: uuid.UUID
    branch_name: str
    branch_code: str
    building_count: int
    floor_count: int
    department_count: int
    reception_desk_count: int
    security_gate_count: int
    active_employee_count: int


class CrossBranchRollupOut(CamelModel):
    """Read-only structural rollup across every branch in the tenant — org
    chart footprint (buildings/floors/departments/desks/gates) and active
    headcount, not visit/check-in activity: no visit data exists yet (the
    `checkin` feature isn't built), so this reports what's provisionable
    today rather than a placeholder for later.
    """

    branches: list[BranchRollupOut]
    total_branches: int
    total_buildings: int
    total_floors: int
    total_departments: int
    total_reception_desks: int
    total_security_gates: int
    total_active_employees: int

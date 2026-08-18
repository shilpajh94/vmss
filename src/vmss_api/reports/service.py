from sqlalchemy.ext.asyncio import AsyncSession

from vmss_api.reports.repository import BranchRollupRepository
from vmss_api.reports.schemas import BranchRollupOut, CrossBranchRollupOut


async def get_cross_branch_rollup(tenant_db: AsyncSession) -> CrossBranchRollupOut:
    repo = BranchRollupRepository(tenant_db)
    branches = await repo.branches()
    building_counts = await repo.building_counts_by_branch()
    floor_counts = await repo.floor_counts_by_branch()
    department_counts = await repo.department_counts_by_branch()
    reception_desk_counts = await repo.reception_desk_counts_by_branch()
    security_gate_counts = await repo.security_gate_counts_by_branch()
    active_employee_counts = await repo.active_employee_counts_by_branch()

    rows = [
        BranchRollupOut(
            branch_id=branch.id,
            branch_name=branch.name,
            branch_code=branch.code,
            building_count=building_counts.get(branch.id, 0),
            floor_count=floor_counts.get(branch.id, 0),
            department_count=department_counts.get(branch.id, 0),
            reception_desk_count=reception_desk_counts.get(branch.id, 0),
            security_gate_count=security_gate_counts.get(branch.id, 0),
            active_employee_count=active_employee_counts.get(branch.id, 0),
        )
        for branch in branches
    ]
    return CrossBranchRollupOut(
        branches=rows,
        total_branches=len(rows),
        total_buildings=sum(row.building_count for row in rows),
        total_floors=sum(row.floor_count for row in rows),
        total_departments=sum(row.department_count for row in rows),
        total_reception_desks=sum(row.reception_desk_count for row in rows),
        total_security_gates=sum(row.security_gate_count for row in rows),
        total_active_employees=sum(row.active_employee_count for row in rows),
    )

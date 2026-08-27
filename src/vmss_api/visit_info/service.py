import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from vmss_api.auth.repository import UserRepository
from vmss_api.org_structure.repository import DepartmentRepository
from vmss_api.visit_info.repository import VisitDurationRepository, VisitPurposeRepository
from vmss_api.visit_info.schemas import (
    DepartmentLookupOut,
    HostSearchResultOut,
    VisitDurationOut,
    VisitInfoOptionsOut,
    VisitPurposeOut,
)


async def search_hosts(
    tenant_db: AsyncSession, *, query: str | None, limit: int
) -> list[HostSearchResultOut]:
    """`GET /hosts/search`. Resolves each matched employee's department name
    with one batched query, not one query per host (query-performance.md
    §2). A `None` query returns a browsable default list instead of a
    filtered match set.
    """
    hosts = await UserRepository(tenant_db).search_active_by_name_or_email(query, limit=limit)
    department_ids = {host.department_id for host in hosts if host.department_id is not None}
    department_names = await DepartmentRepository(tenant_db).get_names_by_ids(department_ids)
    return [
        HostSearchResultOut(
            id=host.id,
            name=host.full_name,
            email=host.email,
            department=department_names.get(host.department_id) if host.department_id else None,
        )
        for host in hosts
    ]


async def list_departments(
    tenant_db: AsyncSession, *, branch_id: uuid.UUID
) -> list[DepartmentLookupOut]:
    """`GET /visit-info/departments`."""
    departments = await DepartmentRepository(tenant_db).list_active_for_branch(branch_id)
    return [DepartmentLookupOut(id=d.id, name=d.name) for d in departments]


async def get_visit_info_options(tenant_db: AsyncSession) -> VisitInfoOptionsOut:
    """`GET /visit-info/options`."""
    purposes = await VisitPurposeRepository(tenant_db).list_active()
    durations = await VisitDurationRepository(tenant_db).list_active()
    return VisitInfoOptionsOut(
        purposes=[VisitPurposeOut(id=p.id, name=p.name) for p in purposes],
        durations=[VisitDurationOut(id=d.id, name=d.name, minutes=d.minutes) for d in durations],
    )

import uuid

from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from vmss_api.auth.models import User
from vmss_api.core.config import settings
from vmss_api.core.schemas import BranchScope, SortOrder
from vmss_api.org_structure.models import (
    Branch,
    Building,
    Company,
    Department,
    Floor,
    ReceptionDesk,
    SecurityGate,
)
from vmss_api.org_structure.repository import (
    BranchRepository,
    BuildingRepository,
    CompanyRepository,
    DepartmentRepository,
    FloorRepository,
    ReceptionDeskRepository,
    SecurityGateRepository,
)
from vmss_api.org_structure.schemas import (
    BranchCreate,
    BranchProvisionRequest,
    BranchUpdate,
    BuildingCreate,
    BuildingUpdate,
    CompanyCreate,
    CompanyUpdate,
    DepartmentCreate,
    DepartmentUpdate,
    FloorCreate,
    FloorUpdate,
    ReceptionDeskCreate,
    ReceptionDeskUpdate,
    SecurityGateCreate,
    SecurityGateUpdate,
)
from vmss_api.registrations.repository import RegistrationDeviceKeyRepository

# --- Branch-resolution helpers -------------------------------------------
#
# Floor/Department/ReceptionDesk carry no `branch_id` column of their own —
# only Building and SecurityGate do. `resolve_building_branch_id`/
# `resolve_floor_branch_id` walk building_id -> Building, or floor_id ->
# Floor -> Building, and are used two ways:
#   - by `router.py`'s creation endpoints, to resolve a branch id from the
#     payload for `org_structure/deps.py::authorize_branch_id`, since
#     `X-Branch-ID` is no longer read there;
#   - by the get/update/delete functions below, which fetch the entity and
#     check `user.has_permission(code, branch_id=<the entity's real branch>)`
#     directly — a caller with no access is met with 404, not 403, so a
#     branch-scoped caller can't tell "doesn't exist" apart from "exists,
#     but in a branch you can't see", same tenant-isolation posture used
#     elsewhere in this codebase.


async def _commit_or_conflict(tenant_db: AsyncSession, conflict_detail: str) -> None:
    """Commits, translating a residual check-then-insert race on one of the
    partial unique indexes (`models.py`'s `_NOT_DELETED` indexes; see
    `openspec/changes/harden-org-structure-crud/design.md` Decision 2) into
    the same 409 the pre-check already raises for the common case, instead
    of an unhandled `IntegrityError` reaching the client — mirroring
    `auth/service.py::sync_employee_directory`'s existing pattern.
    """
    try:
        await tenant_db.commit()
    except IntegrityError as exc:
        await tenant_db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, detail=conflict_detail) from exc


async def resolve_building_branch_id(
    tenant_db: AsyncSession, building_id: uuid.UUID
) -> uuid.UUID | None:
    building = await BuildingRepository(tenant_db).get(building_id)
    return building.branch_id if building is not None else None


async def resolve_floor_branch_id(tenant_db: AsyncSession, floor_id: uuid.UUID) -> uuid.UUID | None:
    floor = await FloorRepository(tenant_db).get(floor_id)
    if floor is None:
        return None
    return await resolve_building_branch_id(tenant_db, floor.building_id)


async def _resolve_building_branch_id_tolerant(
    tenant_db: AsyncSession, building_id: uuid.UUID
) -> uuid.UUID | None:
    """Same as `resolve_building_branch_id`, but tolerates the building
    itself having been soft-deleted — for resolving the branch of an
    *existing* Floor/desk whose own row was never deleted, so it doesn't
    become a permanent 404 the moment an ancestor is removed. Never use this
    for create-time validation, where a soft-deleted parent must still be
    treated as absent.
    """
    building = await BuildingRepository(tenant_db).get_including_deleted(building_id)
    return building.branch_id if building is not None else None


async def _resolve_floor_branch_id_tolerant(
    tenant_db: AsyncSession, floor_id: uuid.UUID
) -> uuid.UUID | None:
    floor = await FloorRepository(tenant_db).get_including_deleted(floor_id)
    if floor is None:
        return None
    return await _resolve_building_branch_id_tolerant(tenant_db, floor.building_id)


# --- Company (singleton) -----------------------------------------------


async def create_company(tenant_db: AsyncSession, payload: CompanyCreate) -> Company:
    repo = CompanyRepository(tenant_db)
    if await repo.get_singleton() is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, detail="Company already configured")
    if (
        payload.registration_number is not None
        and await repo.get_by_registration_number(payload.registration_number) is not None
    ):
        raise HTTPException(status.HTTP_409_CONFLICT, detail="Registration number already exists")
    company = Company(id=uuid.uuid4(), **payload.model_dump())
    tenant_db.add(company)
    await _commit_or_conflict(tenant_db, "Registration number already exists")
    await tenant_db.refresh(company)
    return company


async def get_company(tenant_db: AsyncSession) -> Company:
    company = await CompanyRepository(tenant_db).get_singleton()
    if company is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Company not configured yet")
    return company


async def update_company(tenant_db: AsyncSession, payload: CompanyUpdate) -> Company:
    repo = CompanyRepository(tenant_db)
    company = await repo.get_singleton()
    if company is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Company not configured yet")
    changes = payload.model_dump(exclude_unset=True)
    new_registration_number = changes.get("registration_number")
    if (
        new_registration_number is not None
        and new_registration_number != company.registration_number
        and await repo.get_by_registration_number(new_registration_number) is not None
    ):
        raise HTTPException(status.HTTP_409_CONFLICT, detail="Registration number already exists")
    for field, value in changes.items():
        setattr(company, field, value)
    await _commit_or_conflict(tenant_db, "Registration number already exists")
    await tenant_db.refresh(company)
    return company


async def delete_company(tenant_db: AsyncSession) -> None:
    repo = CompanyRepository(tenant_db)
    company = await repo.get_singleton()
    if company is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Company not configured yet")
    await repo.soft_delete(company)
    await tenant_db.commit()


# --- Branch --------------------------------------------------------------


async def create_branch(tenant_db: AsyncSession, payload: BranchCreate) -> Branch:
    repo = BranchRepository(tenant_db)
    if await repo.get_by_code(payload.code) is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, detail="Branch code already exists")
    branch = Branch(id=uuid.uuid4(), **payload.model_dump())
    tenant_db.add(branch)
    await _commit_or_conflict(tenant_db, "Branch code already exists")
    await tenant_db.refresh(branch)
    return branch


async def list_branches_page(
    tenant_db: AsyncSession,
    *,
    branch_scope: BranchScope,
    page: int,
    page_size: int,
    sort_by: str,
    sort_order: SortOrder,
) -> tuple[list[Branch], int]:
    return await BranchRepository(tenant_db).list_page(
        branch_scope=branch_scope,
        page=page,
        page_size=page_size,
        sort_by=sort_by,
        sort_order=sort_order,
    )


async def _get_branch_or_404(tenant_db: AsyncSession, branch_id: uuid.UUID) -> Branch:
    branch = await BranchRepository(tenant_db).get(branch_id)
    if branch is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Branch not found")
    return branch


async def get_branch(
    tenant_db: AsyncSession, branch_id: uuid.UUID, user: User, permission_code: str
) -> Branch:
    """`permission_code` check mirrors `get_building`'s pattern: a
    branch-scoped role only holds `branches:view` at its own branch(es), so
    checking it here (rather than the blanket, company-wide-only
    `require_permission` the route used to depend on) is what lets a
    non-admin caller see the one branch they belong to at all.
    """
    branch = await _get_branch_or_404(tenant_db, branch_id)
    if not user.has_permission(permission_code, branch_id=branch.id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Branch not found")
    return branch


async def update_branch(
    tenant_db: AsyncSession, branch_id: uuid.UUID, payload: BranchUpdate
) -> Branch:
    """No permission re-check here: the route's `branches:manage` dependency
    is deliberately company-wide-only (see `router.py`'s "Company-wide only,
    not branch-scoped" note), so by the time this runs the caller is already
    known to be authorized for every branch.

    No walk-in-registration-default guard is needed here (contrast
    `delete_branch`): `BranchUpdate` has no `code` field at all, so a
    branch's `code` can never be renamed through this endpoint in the first
    place — there's no reachable path for this update to silently break the
    no-device-key walk-in fallback.
    """
    branch = await _get_branch_or_404(tenant_db, branch_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(branch, field, value)
    await tenant_db.commit()
    await tenant_db.refresh(branch)
    return branch


async def delete_branch(
    tenant_db: AsyncSession, branch_id: uuid.UUID, global_db: AsyncSession
) -> None:
    """Blocked (409) while the branch still has an active org-chart
    descendant, an active walk-in device credential, or is itself the
    branch currently configured as the walk-in registration default
    (`settings.registration_default_branch_code`) — mirrors
    `auth/service.py::delete_role`'s `has_active_grants()` guard. Without
    this, soft-deleting a branch silently orphans a live
    `RegistrationDeviceKey`, or silently breaks the no-device-key fallback
    that resolves its branch by matching this exact code, and either
    kiosk starts failing walk-in registration with no indication why (the
    original bugs this guard closes).
    """
    repo = BranchRepository(tenant_db)
    branch = await _get_branch_or_404(tenant_db, branch_id)
    if branch.code == settings.registration_default_branch_code:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail="Branch is configured as the walk-in registration default and cannot be deleted",
        )
    if await repo.has_active_org_chart_descendants(branch.id):
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail=(
                "Branch has active buildings, floors, departments, reception "
                "desks, or security gates and cannot be deleted"
            ),
        )
    if await RegistrationDeviceKeyRepository(global_db).has_active_key_for_branch(branch.id):
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail="Branch has an active registration device credential and cannot be deleted",
        )
    await repo.soft_delete(branch)
    await tenant_db.commit()


# --- Branch provisioning (bulk bootstrap) ---------------------------------


class ProvisionCounts:
    """Plain counter bag returned alongside the new `Branch` — the router
    maps this straight onto `schemas.BranchProvisionResponse`.
    """

    __slots__ = ("buildings", "departments", "floors", "reception_desks", "security_gates")

    def __init__(self) -> None:
        self.buildings = 0
        self.floors = 0
        self.departments = 0
        self.reception_desks = 0
        self.security_gates = 0


def _reject_duplicate(seen: set[str], code: str, *, what: str) -> None:
    if code in seen:
        raise HTTPException(
            status.HTTP_409_CONFLICT, detail=f"Duplicate {what} code {code!r} in request"
        )
    seen.add(code)


async def provision_branch(
    tenant_db: AsyncSession, payload: BranchProvisionRequest
) -> tuple[Branch, ProvisionCounts]:
    """Scaffolds a brand-new `Branch` plus as much of its Building -> Floor
    -> Department/ReceptionDesk chain and SecurityGates as the payload
    supplies, in one transaction. Every row's id is generated up front
    (`uuid.uuid4()`) so foreign keys can be wired immediately, without a
    round trip per level — the whole tree is `session.add()`-ed and
    committed exactly once (query-performance.md §3's "commit once per
    logical operation," applied to a bulk create rather than a bulk
    update). If any uniqueness check below fails, nothing has been
    committed yet, so there's no partial branch left behind to clean up.

    Per-entity uniqueness is still checked against what's already in the
    database (same rules `create_building`/`create_floor`/... enforce
    individually) *and* against sibling entries within this same request,
    since none of those siblings have hit the database yet for a `SELECT`
    to catch a collision between them.
    """
    branch_repo = BranchRepository(tenant_db)
    if await branch_repo.get_by_code(payload.code) is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, detail="Branch code already exists")

    branch = Branch(id=uuid.uuid4(), name=payload.name, code=payload.code, address=payload.address)
    tenant_db.add(branch)
    # No ORM `relationship()` links `Branch`/`Building`/`Floor`/... to each
    # other (only raw FK columns — see org_structure/models.py), so the
    # flush's cross-class insert ordering isn't guided by a dependency graph
    # the way it would be with declared relationships. An explicit `flush()`
    # after each parent is added, before any child referencing its id is
    # added, forces the parent's row to exist in the database first — same
    # fix `rbac_catalog.py::seed_default_roles` applies between permissions
    # and roles. Still one `commit()` for the whole tree at the end.
    await tenant_db.flush()

    counts = ProvisionCounts()
    seen_building_codes: set[str] = set()
    seen_gate_codes: set[str] = set()
    # Department uniqueness is now branch-scoped (design.md Decision 4), not
    # per-floor, so this set is shared across every floor/building in the
    # request rather than reset per floor.
    seen_department_codes: set[str] = set()

    for building_payload in payload.buildings:
        _reject_duplicate(seen_building_codes, building_payload.code, what="building")

        building = Building(
            id=uuid.uuid4(),
            branch_id=branch.id,
            name=building_payload.name,
            code=building_payload.code,
            address=building_payload.address,
        )
        tenant_db.add(building)
        await tenant_db.flush()
        counts.buildings += 1

        seen_floor_numbers: set[int] = set()
        for floor_payload in building_payload.floors:
            if floor_payload.floor_number in seen_floor_numbers:
                raise HTTPException(
                    status.HTTP_409_CONFLICT,
                    detail=(
                        f"Duplicate floor number {floor_payload.floor_number} in building "
                        f"{building_payload.code!r}"
                    ),
                )
            seen_floor_numbers.add(floor_payload.floor_number)

            floor = Floor(
                id=uuid.uuid4(),
                building_id=building.id,
                name=floor_payload.name,
                floor_number=floor_payload.floor_number,
            )
            tenant_db.add(floor)
            await tenant_db.flush()
            counts.floors += 1

            for department_payload in floor_payload.departments:
                _reject_duplicate(seen_department_codes, department_payload.code, what="department")
                tenant_db.add(
                    Department(
                        id=uuid.uuid4(),
                        branch_id=branch.id,
                        floor_id=floor.id,
                        name=department_payload.name,
                        code=department_payload.code,
                    )
                )
                counts.departments += 1

            seen_desk_codes: set[str] = set()
            for desk_payload in floor_payload.reception_desks:
                _reject_duplicate(seen_desk_codes, desk_payload.code, what="reception desk")
                tenant_db.add(
                    ReceptionDesk(
                        id=uuid.uuid4(),
                        floor_id=floor.id,
                        name=desk_payload.name,
                        code=desk_payload.code,
                    )
                )
                counts.reception_desks += 1

        for gate_payload in building_payload.security_gates:
            _reject_duplicate(seen_gate_codes, gate_payload.code, what="security gate")
            tenant_db.add(
                SecurityGate(
                    id=uuid.uuid4(),
                    branch_id=branch.id,
                    building_id=building.id,
                    name=gate_payload.name,
                    code=gate_payload.code,
                    gate_type=gate_payload.gate_type.value,
                )
            )
            counts.security_gates += 1

    for gate_payload in payload.security_gates:
        _reject_duplicate(seen_gate_codes, gate_payload.code, what="security gate")
        tenant_db.add(
            SecurityGate(
                id=uuid.uuid4(),
                branch_id=branch.id,
                building_id=None,
                name=gate_payload.name,
                code=gate_payload.code,
                gate_type=gate_payload.gate_type.value,
            )
        )
        counts.security_gates += 1

    await _commit_or_conflict(tenant_db, "One or more codes already exist")
    await tenant_db.refresh(branch)
    return branch, counts


# --- Building --------------------------------------------------------------
#
# Branch-scoped: creation resolves its branch from `payload.branch_id`
# (`org_structure/router.py` via `org_structure/deps.py::authorize_branch_id`
# — `X-Branch-ID` is not read here). Get/update/delete authorize against the
# fetched entity's own `branch_id` instead of a header-resolved one.


async def create_building(tenant_db: AsyncSession, payload: BuildingCreate) -> Building:
    repo = BuildingRepository(tenant_db)
    if await repo.get_by_code(payload.branch_id, payload.code) is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, detail="Building code already exists")
    building = Building(id=uuid.uuid4(), **payload.model_dump())
    tenant_db.add(building)
    await _commit_or_conflict(tenant_db, "Building code already exists")
    await tenant_db.refresh(building)
    return building


async def list_buildings_page(
    tenant_db: AsyncSession,
    *,
    branch_scope: BranchScope,
    page: int,
    page_size: int,
    sort_by: str,
    sort_order: SortOrder,
) -> tuple[list[Building], int]:
    return await BuildingRepository(tenant_db).list_page(
        branch_scope=branch_scope,
        page=page,
        page_size=page_size,
        sort_by=sort_by,
        sort_order=sort_order,
    )


async def get_building(
    tenant_db: AsyncSession, building_id: uuid.UUID, user: User, permission_code: str
) -> Building:
    building = await BuildingRepository(tenant_db).get(building_id)
    if building is None or not user.has_permission(permission_code, branch_id=building.branch_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Building not found")
    return building


async def update_building(
    tenant_db: AsyncSession,
    building_id: uuid.UUID,
    payload: BuildingUpdate,
    user: User,
) -> Building:
    repo = BuildingRepository(tenant_db)
    building = await get_building(tenant_db, building_id, user, "buildings:manage")
    changes = payload.model_dump(exclude_unset=True)
    new_code = changes.get("code")
    if (
        new_code is not None
        and new_code != building.code
        and await repo.get_by_code(building.branch_id, new_code) is not None
    ):
        raise HTTPException(status.HTTP_409_CONFLICT, detail="Building code already exists")
    for field, value in changes.items():
        setattr(building, field, value)
    await _commit_or_conflict(tenant_db, "Building code already exists")
    await tenant_db.refresh(building)
    return building


async def delete_building(tenant_db: AsyncSession, building_id: uuid.UUID, user: User) -> None:
    repo = BuildingRepository(tenant_db)
    building = await get_building(tenant_db, building_id, user, "buildings:manage")
    await repo.soft_delete(building)
    await tenant_db.commit()


# --- Floor --------------------------------------------------------------


async def create_floor(
    tenant_db: AsyncSession, payload: FloorCreate, authorized_branch_id: uuid.UUID
) -> Floor:
    branch_id = await resolve_building_branch_id(tenant_db, payload.building_id)
    if branch_id is None or branch_id != authorized_branch_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Building not found")
    repo = FloorRepository(tenant_db)
    if await repo.get_by_number(payload.building_id, payload.floor_number) is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, detail="Floor number already exists")
    data = payload.model_dump()
    if data.get("capacity_type") is not None:
        data["capacity_type"] = data["capacity_type"].value
    if data.get("access_level") is not None:
        data["access_level"] = data["access_level"].value
    floor = Floor(id=uuid.uuid4(), **data)
    tenant_db.add(floor)
    await _commit_or_conflict(tenant_db, "Floor number already exists")
    await tenant_db.refresh(floor)
    return floor


async def list_floors_page(
    tenant_db: AsyncSession,
    *,
    branch_scope: BranchScope,
    building_id: uuid.UUID | None,
    page: int,
    page_size: int,
    sort_by: str,
    sort_order: SortOrder,
) -> tuple[list[Floor], int]:
    return await FloorRepository(tenant_db).list_page(
        branch_scope=branch_scope,
        building_id=building_id,
        page=page,
        page_size=page_size,
        sort_by=sort_by,
        sort_order=sort_order,
    )


async def get_floor(
    tenant_db: AsyncSession, floor_id: uuid.UUID, user: User, permission_code: str
) -> Floor:
    floor = await FloorRepository(tenant_db).get(floor_id)
    if floor is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Floor not found")
    branch_id = await _resolve_building_branch_id_tolerant(tenant_db, floor.building_id)
    if branch_id is None or not user.has_permission(permission_code, branch_id=branch_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Floor not found")
    return floor


async def update_floor(
    tenant_db: AsyncSession,
    floor_id: uuid.UUID,
    payload: FloorUpdate,
    user: User,
) -> Floor:
    repo = FloorRepository(tenant_db)
    floor = await get_floor(tenant_db, floor_id, user, "floors:manage")
    changes = payload.model_dump(exclude_unset=True)
    new_number = changes.get("floor_number")
    if (
        new_number is not None
        and new_number != floor.floor_number
        and await repo.get_by_number(floor.building_id, new_number) is not None
    ):
        raise HTTPException(status.HTTP_409_CONFLICT, detail="Floor number already exists")
    if changes.get("capacity_type") is not None:
        changes["capacity_type"] = changes["capacity_type"].value
    if changes.get("access_level") is not None:
        changes["access_level"] = changes["access_level"].value
    for field, value in changes.items():
        setattr(floor, field, value)
    await _commit_or_conflict(tenant_db, "Floor number already exists")
    await tenant_db.refresh(floor)
    return floor


async def delete_floor(tenant_db: AsyncSession, floor_id: uuid.UUID, user: User) -> None:
    repo = FloorRepository(tenant_db)
    floor = await get_floor(tenant_db, floor_id, user, "floors:manage")
    await repo.soft_delete(floor)
    await tenant_db.commit()


# --- Department --------------------------------------------------------------


async def create_department(tenant_db: AsyncSession, payload: DepartmentCreate) -> Department:
    if payload.floor_id is not None:
        floor_branch_id = await resolve_floor_branch_id(tenant_db, payload.floor_id)
        if floor_branch_id != payload.branch_id:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Floor not found")
    repo = DepartmentRepository(tenant_db)
    if await repo.get_by_code(payload.branch_id, payload.code) is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, detail="Department code already exists")
    department = Department(id=uuid.uuid4(), **payload.model_dump())
    tenant_db.add(department)
    await _commit_or_conflict(tenant_db, "Department code already exists")
    await tenant_db.refresh(department)
    return department


async def list_departments_page(
    tenant_db: AsyncSession,
    *,
    branch_scope: BranchScope,
    floor_id: uuid.UUID | None,
    page: int,
    page_size: int,
    sort_by: str,
    sort_order: SortOrder,
) -> tuple[list[Department], int]:
    return await DepartmentRepository(tenant_db).list_page(
        branch_scope=branch_scope,
        floor_id=floor_id,
        page=page,
        page_size=page_size,
        sort_by=sort_by,
        sort_order=sort_order,
    )


async def get_department(
    tenant_db: AsyncSession, department_id: uuid.UUID, user: User, permission_code: str
) -> Department:
    department = await DepartmentRepository(tenant_db).get(department_id)
    if department is None or not user.has_permission(
        permission_code, branch_id=department.branch_id
    ):
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Department not found")
    return department


async def update_department(
    tenant_db: AsyncSession,
    department_id: uuid.UUID,
    payload: DepartmentUpdate,
    user: User,
) -> Department:
    repo = DepartmentRepository(tenant_db)
    department = await get_department(tenant_db, department_id, user, "departments:manage")
    changes = payload.model_dump(exclude_unset=True)
    new_code = changes.get("code")
    if (
        new_code is not None
        and new_code != department.code
        and await repo.get_by_code(department.branch_id, new_code) is not None
    ):
        raise HTTPException(status.HTTP_409_CONFLICT, detail="Department code already exists")
    new_floor_id = changes.get("floor_id")
    if new_floor_id is not None:
        floor_branch_id = await resolve_floor_branch_id(tenant_db, new_floor_id)
        if floor_branch_id != department.branch_id:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Floor not found")
    for field, value in changes.items():
        setattr(department, field, value)
    await _commit_or_conflict(tenant_db, "Department code already exists")
    await tenant_db.refresh(department)
    return department


async def delete_department(tenant_db: AsyncSession, department_id: uuid.UUID, user: User) -> None:
    repo = DepartmentRepository(tenant_db)
    department = await get_department(tenant_db, department_id, user, "departments:manage")
    await repo.soft_delete(department)
    await tenant_db.commit()


# --- Reception Desk --------------------------------------------------------------


async def create_reception_desk(
    tenant_db: AsyncSession, payload: ReceptionDeskCreate, authorized_branch_id: uuid.UUID
) -> ReceptionDesk:
    branch_id = await resolve_floor_branch_id(tenant_db, payload.floor_id)
    if branch_id is None or branch_id != authorized_branch_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Floor not found")
    repo = ReceptionDeskRepository(tenant_db)
    if await repo.get_by_code(payload.floor_id, payload.code) is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, detail="Desk code already exists")
    data = payload.model_dump()
    data["status"] = data["status"].value
    desk = ReceptionDesk(id=uuid.uuid4(), **data)
    tenant_db.add(desk)
    await _commit_or_conflict(tenant_db, "Desk code already exists")
    await tenant_db.refresh(desk)
    return desk


async def list_reception_desks_page(
    tenant_db: AsyncSession,
    *,
    branch_scope: BranchScope,
    floor_id: uuid.UUID | None,
    page: int,
    page_size: int,
    sort_by: str,
    sort_order: SortOrder,
) -> tuple[list[ReceptionDesk], int]:
    return await ReceptionDeskRepository(tenant_db).list_page(
        branch_scope=branch_scope,
        floor_id=floor_id,
        page=page,
        page_size=page_size,
        sort_by=sort_by,
        sort_order=sort_order,
    )


async def get_reception_desk(
    tenant_db: AsyncSession, desk_id: uuid.UUID, user: User, permission_code: str
) -> ReceptionDesk:
    desk = await ReceptionDeskRepository(tenant_db).get(desk_id)
    if desk is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Desk not found")
    branch_id = await _resolve_floor_branch_id_tolerant(tenant_db, desk.floor_id)
    if branch_id is None or not user.has_permission(permission_code, branch_id=branch_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Desk not found")
    return desk


async def update_reception_desk(
    tenant_db: AsyncSession,
    desk_id: uuid.UUID,
    payload: ReceptionDeskUpdate,
    user: User,
) -> ReceptionDesk:
    repo = ReceptionDeskRepository(tenant_db)
    desk = await get_reception_desk(tenant_db, desk_id, user, "desks:manage")
    changes = payload.model_dump(exclude_unset=True)
    new_code = changes.get("code")
    if (
        new_code is not None
        and new_code != desk.code
        and await repo.get_by_code(desk.floor_id, new_code) is not None
    ):
        raise HTTPException(status.HTTP_409_CONFLICT, detail="Desk code already exists")
    if "status" in changes and changes["status"] is not None:
        changes["status"] = changes["status"].value
    for field, value in changes.items():
        setattr(desk, field, value)
    await _commit_or_conflict(tenant_db, "Desk code already exists")
    await tenant_db.refresh(desk)
    return desk


async def delete_reception_desk(tenant_db: AsyncSession, desk_id: uuid.UUID, user: User) -> None:
    repo = ReceptionDeskRepository(tenant_db)
    desk = await get_reception_desk(tenant_db, desk_id, user, "desks:manage")
    await repo.soft_delete(desk)
    await tenant_db.commit()


# --- Security Gate --------------------------------------------------------------


async def create_security_gate(
    tenant_db: AsyncSession, payload: SecurityGateCreate
) -> SecurityGate:
    if payload.building_id is not None:
        building_branch_id = await resolve_building_branch_id(tenant_db, payload.building_id)
        if building_branch_id != payload.branch_id:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Building not found")
    repo = SecurityGateRepository(tenant_db)
    if await repo.get_by_code(payload.branch_id, payload.code) is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, detail="Gate code already exists")
    data = payload.model_dump()
    data["gate_type"] = data["gate_type"].value
    gate = SecurityGate(id=uuid.uuid4(), **data)
    tenant_db.add(gate)
    await _commit_or_conflict(tenant_db, "Gate code already exists")
    await tenant_db.refresh(gate)
    return gate


async def list_security_gates_page(
    tenant_db: AsyncSession,
    *,
    branch_scope: BranchScope,
    building_id: uuid.UUID | None,
    page: int,
    page_size: int,
    sort_by: str,
    sort_order: SortOrder,
) -> tuple[list[SecurityGate], int]:
    return await SecurityGateRepository(tenant_db).list_page(
        branch_scope=branch_scope,
        building_id=building_id,
        page=page,
        page_size=page_size,
        sort_by=sort_by,
        sort_order=sort_order,
    )


async def get_security_gate(
    tenant_db: AsyncSession, gate_id: uuid.UUID, user: User, permission_code: str
) -> SecurityGate:
    gate = await SecurityGateRepository(tenant_db).get(gate_id)
    if gate is None or not user.has_permission(permission_code, branch_id=gate.branch_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Gate not found")
    return gate


async def update_security_gate(
    tenant_db: AsyncSession,
    gate_id: uuid.UUID,
    payload: SecurityGateUpdate,
    user: User,
) -> SecurityGate:
    repo = SecurityGateRepository(tenant_db)
    gate = await get_security_gate(tenant_db, gate_id, user, "gates:manage")
    changes = payload.model_dump(exclude_unset=True)
    new_code = changes.get("code")
    if (
        new_code is not None
        and new_code != gate.code
        and await repo.get_by_code(gate.branch_id, new_code) is not None
    ):
        raise HTTPException(status.HTTP_409_CONFLICT, detail="Gate code already exists")
    if changes.get("building_id") is not None:
        building_branch_id = await resolve_building_branch_id(tenant_db, changes["building_id"])
        if building_branch_id != gate.branch_id:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Building not found")
    if "gate_type" in changes and changes["gate_type"] is not None:
        changes["gate_type"] = changes["gate_type"].value
    for field, value in changes.items():
        setattr(gate, field, value)
    await _commit_or_conflict(tenant_db, "Gate code already exists")
    await tenant_db.refresh(gate)
    return gate


async def delete_security_gate(tenant_db: AsyncSession, gate_id: uuid.UUID, user: User) -> None:
    repo = SecurityGateRepository(tenant_db)
    gate = await get_security_gate(tenant_db, gate_id, user, "gates:manage")
    await repo.soft_delete(gate)
    await tenant_db.commit()

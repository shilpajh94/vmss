"""The default permission/role catalog every tenant schema is seeded with at
provisioning time (`platform/service.py::create_tenant`), and reused as-is by
`scripts/seed_dev_data.py` for local development. Single source of truth so the
two never drift apart.

The five role names below (`ROLE_PERMISSIONS`' keys) are also the canonical
list of standard, non-deletable, non-renameable roles enforced by
`auth/service.py`'s role-management functions — see
`openspec/changes/add-role-management-and-org-field-gaps/design.md` Decision 1.
"""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from vmss_api.auth.models import Permission, Role

# The full permission catalog grows as features are built — start with what
# the skeleton actually has wired up.
PERMISSION_CODES = [
    "tenants:read",
    "tenants:update",
    "visitors:print_badge",
    "timeline:view",
    "branches:manage",
    "branches:view",
    "branches:provision",
    "reports:view",
    "users:manage",
    "companies:manage",
    "companies:view",
    "buildings:manage",
    "buildings:view",
    "floors:manage",
    "floors:view",
    "departments:manage",
    "departments:view",
    "desks:manage",
    "desks:view",
    "gates:manage",
    "gates:view",
    "employees:manage",
    "employees:view",
    "visitor-categories:manage",
    "visitor-categories:view",
    "form-builder:manage",
    "form-builder:view",
    "approval-workflow-rules:manage",
    "approval-workflow-rules:view",
    "invitations:create",
    "invitations:view",
    "invitations:view-all",
    "invitations:cancel",
    "invitations:approve",
    "invitations:approve-override",
    "invitations:deny",
    "invitations:revert-approval",
    "invitations:checkin",
    "invitations:checkout",
    "invitations:reschedule",
    "invitations:extend",
    "invitations:edit",
    "invitations:badge",
    "invitations:watchlist-override",
    "invitations:export",
    "invitations:clear-all",
    "documents:view",
    "roles:manage",
    "roles:view",
    "sso-config:manage",
    "sso-config:view",
    "kiosks:manage",
    "kiosks:view",
    "devices:view",
    "devices:manage",
    "devices:approve",
    "settings:view",
    "settings:manage",
    "audit-logs:view",
    "audit-logs:export",
]

# The five standard roles per security-architecture.md §1. Admin is granted
# company-wide (branch_id=None) by whoever assigns it; the others are meant to
# be assigned per branch/location as staff are onboarded there — seeding
# grants no branch assignments, only the role rows themselves, ready for
# `POST /auth/users/{id}/branch-roles` to grant.
ROLE_PERMISSIONS: dict[str, list[str]] = {
    "admin": PERMISSION_CODES,
    "reception": [
        "tenants:read",
        "branches:view",
        "buildings:view",
        "departments:view",
        "employees:view",
        "desks:view",
        "visitor-categories:view",
        "approval-workflow-rules:view",
        "invitations:create",
        "invitations:view",
        "invitations:view-all",
        "invitations:approve",
        "invitations:deny",
        "invitations:revert-approval",
        "invitations:checkout",
        "invitations:reschedule",
        "invitations:extend",
        "invitations:edit",
        "invitations:badge",
        "invitations:export",
        "visitors:print_badge",
        "timeline:view",
        "documents:view",
        "roles:view",
    ],
    "security": [
        "tenants:read",
        "branches:view",
        "buildings:view",
        "departments:view",
        "employees:view",
        "gates:view",
        "invitations:view",
        "invitations:view-all",
        "invitations:checkin",
        "invitations:checkout",
        "invitations:export",
        "timeline:view",
        "documents:view",
    ],
    "host": [
        "tenants:read",
        "branches:view",
        "buildings:view",
        "departments:view",
        "employees:view",
        "visitor-categories:view",
        "approval-workflow-rules:view",
        "invitations:create",
        "invitations:view",
        "invitations:approve",
        "invitations:deny",
        "invitations:revert-approval",
        "invitations:reschedule",
        "invitations:extend",
        "invitations:edit",
        "roles:view",
    ],
    # Exists only so the catalog literally lists all five names API-02
    # requires. Visitors never authenticate through this JWT/RBAC system
    # (security-architecture.md §2 — visitor flows are unauthenticated,
    # signed-token/QR based), so this grants nothing and is enforced as
    # non-assignable to a `User` in `service.py::assign_branch_role`.
    "visitor": [],
}

# The five standard role names, exported so `auth/service.py` can reject a
# rename/delete of any of them without duplicating this list — see the
# module docstring above.
STANDARD_ROLE_NAMES = frozenset(ROLE_PERMISSIONS.keys())

# Roles that must never be `Company.default_host_role_id`
# (`org_structure/service.py`) — the role stepOrder-0's *ownership* step is
# created for. `host` is excluded because the ownership step's whole job is
# to be delegated *to* a host by whoever holds this role (normally
# Reception); making the ownership step itself host-identified would be
# circular. `visitor` is excluded for the same reason
# `auth/service.py::assign_branch_role` already refuses to assign it to a
# `User` — it's not a real staff role, so it can never legitimately hold or
# match a workflow step either.
NON_APPROVER_ROLE_NAMES = frozenset({"host", "visitor"})

# Roles that must never be wired as an `ApprovalWorkflowRule.approver_role_id`
# (`visitors/service.py`). Unlike `NON_APPROVER_ROLE_NAMES` above, `host` IS
# allowed here — a workflow's stepOrder 1+ can legitimately be host-identified
# (e.g. "Reception -> Host -> Manager") — see `DELEGATION_ONLY_ROLE_NAMES`
# below for how that step's activation is kept from broadcasting to every
# host-eligible employee. `visitor` stays excluded — not a real staff role.
NON_WORKFLOW_STEP_ROLE_NAMES = frozenset({"visitor"})

# Roles for which a step must never be actionable (or notified) by "any
# holder of the role" the way Security/Manager steps are — only by whoever
# the step is explicitly `delegated_to_user_id` (`approvals/models.py`), by
# the invitation's already-resolved host, or by an `invitations:approve-
# override` holder. `host` is the only one today: it is typically held by a
# large, company-wide set of people, so a fresh host-identified step must
# wait for Reception (or the previous step's approver) to delegate it to one
# specific person before anyone can act on it or gets pushed a notification
# about it (`approvals/service.py::_caller_matches_step`,
# `notifications/service.py::notify_step_approver`) — otherwise every
# host-eligible employee would see and be able to act on a request nobody
# delegated to them.
DELEGATION_ONLY_ROLE_NAMES = frozenset({"host"})


async def seed_default_roles(tenant_db: AsyncSession) -> None:
    """Idempotent: safe to call on a tenant schema that's already seeded
    (check-before-insert on both permission code and role name), matching
    `create_tenant`'s existing "a retry can finish partial provisioning"
    posture (`platform/service.py`).

    Also backfills any permission code added to `PERMISSION_CODES`/
    `ROLE_PERMISSIONS` *after* a standard role was first seeded onto an
    existing tenant schema — without this, a tenant provisioned before, say,
    `invitations:create` existed would have its "admin" role permanently
    stuck missing it forever, since nothing else ever re-syncs an existing
    role's permission set against the current catalog (confirmed directly:
    this is exactly what made the local dev tenant's seeded admin unable to
    create an invitation). This is a union merge — it only ever adds a
    catalog-defined permission the role is missing, never removes one, so a
    deliberate custom grant beyond the standard catalog survives.
    """
    permission_stmt = select(Permission).where(Permission.code.in_(PERMISSION_CODES))
    existing_permissions = (await tenant_db.execute(permission_stmt)).scalars().all()
    existing_codes = {p.code for p in existing_permissions}
    new_permissions = [
        Permission(id=uuid.uuid4(), code=code, description=code)
        for code in PERMISSION_CODES
        if code not in existing_codes
    ]
    tenant_db.add_all(new_permissions)
    await tenant_db.flush()
    permissions_by_code = {p.code: p for p in [*existing_permissions, *new_permissions]}

    role_stmt = (
        select(Role)
        .where(Role.name.in_(ROLE_PERMISSIONS.keys()))
        .options(selectinload(Role.permissions))
    )
    existing_roles_by_name = {
        r.name: r for r in (await tenant_db.execute(role_stmt)).scalars().all()
    }
    new_roles = [
        Role(
            id=uuid.uuid4(),
            name=name,
            permissions=[permissions_by_code[code] for code in codes],
        )
        for name, codes in ROLE_PERMISSIONS.items()
        if name not in existing_roles_by_name
    ]
    tenant_db.add_all(new_roles)

    for name, codes in ROLE_PERMISSIONS.items():
        role = existing_roles_by_name.get(name)
        if role is None:
            continue
        current_codes = {p.code for p in role.permissions}
        role.permissions.extend(
            permissions_by_code[code] for code in codes if code not in current_codes
        )

    await tenant_db.flush()

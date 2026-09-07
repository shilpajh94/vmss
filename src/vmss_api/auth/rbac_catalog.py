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
    "approval-workflow-rules:manage",
    "approval-workflow-rules:view",
    "invitations:create",
    "invitations:view",
    "invitations:cancel",
    "invitations:approve",
    "invitations:approve-override",
    "invitations:deny",
    "invitations:checkin",
    "invitations:checkout",
    "invitations:reschedule",
    "invitations:extend",
    "invitations:badge",
    "invitations:watchlist-override",
    "documents:view",
    "roles:manage",
    "roles:view",
    "sso-config:manage",
    "sso-config:view",
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
        "branches:view",
        "buildings:view",
        "departments:view",
        "employees:view",
        "desks:view",
        "visitor-categories:view",
        "invitations:create",
        "invitations:view",
        "invitations:approve",
        "invitations:deny",
        "invitations:reschedule",
        "invitations:extend",
        "invitations:badge",
        "documents:view",
    ],
    "security": [
        "branches:view",
        "buildings:view",
        "departments:view",
        "employees:view",
        "gates:view",
        "invitations:view",
        "invitations:checkin",
        "invitations:checkout",
        "documents:view",
    ],
    "host": [
        "branches:view",
        "buildings:view",
        "departments:view",
        "employees:view",
        "visitor-categories:view",
        "invitations:create",
        "invitations:view",
        "invitations:approve",
        "invitations:deny",
        "invitations:reschedule",
        "invitations:extend",
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

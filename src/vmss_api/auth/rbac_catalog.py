"""The default permission/role catalog every tenant schema is seeded with at
provisioning time (`platform/service.py::create_tenant`), and reused as-is by
`scripts/seed_dev_data.py` for local development. Single source of truth so the
two never drift apart.
"""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

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
        "desks:view",
        "visitor-categories:view",
        "invitations:create",
        "invitations:view",
    ],
    "security": ["branches:view", "gates:view", "invitations:view"],
    "host": [
        "branches:view",
        "visitor-categories:view",
        "invitations:create",
        "invitations:view",
    ],
    # Exists only so the catalog literally lists all five names API-02
    # requires. Visitors never authenticate through this JWT/RBAC system
    # (security-architecture.md §2 — visitor flows are unauthenticated,
    # signed-token/QR based), so this grants nothing and is enforced as
    # non-assignable to a `User` in `service.py::assign_branch_role`.
    "visitor": [],
}


async def seed_default_roles(tenant_db: AsyncSession) -> None:
    """Idempotent: safe to call on a tenant schema that's already seeded
    (check-before-insert on both permission code and role name), matching
    `create_tenant`'s existing "a retry can finish partial provisioning"
    posture (`platform/service.py`).
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

    role_stmt = select(Role).where(Role.name.in_(ROLE_PERMISSIONS.keys()))
    existing_role_names = {r.name for r in (await tenant_db.execute(role_stmt)).scalars().all()}
    new_roles = [
        Role(
            id=uuid.uuid4(),
            name=name,
            permissions=[permissions_by_code[code] for code in codes],
        )
        for name, codes in ROLE_PERMISSIONS.items()
        if name not in existing_role_names
    ]
    tenant_db.add_all(new_roles)
    await tenant_db.flush()

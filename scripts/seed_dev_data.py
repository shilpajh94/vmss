"""Creates a default tenant, branch, RBAC role catalog, and admin user for
local development.

Usage: ddev exec uv run python scripts/seed_dev_data.py
"""

import asyncio
import uuid

import anyio
from sqlalchemy import select

from vmss_api.auth import service as auth_service
from vmss_api.auth.models import Role, UserBranchRole
from vmss_api.auth.rbac_catalog import ROLE_PERMISSIONS, seed_default_roles
from vmss_api.core.config import settings
from vmss_api.core.database import AsyncSessionLocal, tenant_session_scope
from vmss_api.core.security import hash_password
from vmss_api.org_structure.models import Branch
from vmss_api.platform import service as platform_service
from vmss_api.platform.repository import TenantUserIndexRepository
from vmss_api.tenant.repository import TenantRepository

ADMIN_EMAIL = "admin@example.com"
ADMIN_PASSWORD = "admin12345"

DEFAULT_BRANCH_CODE = "MAIN"


async def seed() -> None:
    async with AsyncSessionLocal() as db:
        tenant = await TenantRepository(db).get_by_slug(settings.default_tenant_slug)
        if tenant is None:
            tenant = await platform_service.create_tenant(
                db, name="Default Tenant", slug=settings.default_tenant_slug
            )
            print(f"Provisioned tenant '{tenant.slug}' (schema '{tenant.schema_name}')")
        else:
            # `create_tenant` above already runs every tenant migration once,
            # at creation time — but a tenant that already existed before
            # this run was never re-migrated just because new revisions
            # landed in `alembic_tenant/versions/` since. Re-running this
            # script is the only "bring my dev tenant's schema up to date"
            # step that currently exists, so it has to actually do that, not
            # just skip straight to the admin-user check below. Alembic's
            # own per-schema revision tracking makes this a no-op when
            # already current.
            revision = await anyio.to_thread.run_sync(
                platform_service._run_tenant_migrations_sync, tenant.schema_name
            )
            print(f"Tenant '{tenant.slug}' schema is up to date (revision '{revision}')")

        # Always re-synced, whether or not the admin user already exists:
        # `seed_default_roles` backfills any permission code added to the
        # catalog after this tenant's standard roles were first seeded
        # (rbac_catalog.py's docstring) — the same "re-running this script
        # is the only way to catch a dev tenant up" reasoning as the
        # migration step above, and confirmed necessary the same way: a
        # tenant seeded before `invitations:create` existed would otherwise
        # have its admin role stuck unable to create an invitation forever.
        async with tenant_session_scope(tenant.schema_name) as tenant_db:
            await seed_default_roles(tenant_db)
            await tenant_db.commit()

        already_indexed = await TenantUserIndexRepository(db).get_by_email(ADMIN_EMAIL)
        if already_indexed is not None:
            print(f"Admin user already exists: {ADMIN_EMAIL} (role catalog re-synced)")
            return

        async with tenant_session_scope(tenant.schema_name) as tenant_db:
            role_stmt = select(Role).where(Role.name.in_(ROLE_PERMISSIONS.keys()))
            seeded_roles = (await tenant_db.execute(role_stmt)).scalars().all()
            roles_by_name = {r.name: r for r in seeded_roles}

            branch = Branch(id=uuid.uuid4(), name="Main Branch", code=DEFAULT_BRANCH_CODE)
            tenant_db.add(branch)
            await tenant_db.flush()

            admin_user = await auth_service.create_user(
                tenant_db,
                tenant_id=tenant.id,
                email=ADMIN_EMAIL,
                hashed_password=hash_password(ADMIN_PASSWORD),
                full_name="Admin User",
            )
            tenant_db.add(
                UserBranchRole(
                    id=uuid.uuid4(),
                    user_id=admin_user.id,
                    role_id=roles_by_name["admin"].id,
                    branch_id=None,
                )
            )
            await tenant_db.commit()

        print(
            f"Seeded tenant '{tenant.slug}', branch '{DEFAULT_BRANCH_CODE}', "
            f"role catalog {sorted(ROLE_PERMISSIONS)}, and admin user "
            f"'{ADMIN_EMAIL}' / '{ADMIN_PASSWORD}' (company-wide Admin)"
        )


if __name__ == "__main__":
    asyncio.run(seed())

"""Applies any pending `alembic_tenant` migrations to every tenant, and
re-syncs every tenant's RBAC role grants and default form-builder config
against the current catalog — every run, not just for tenants behind the
migration head, since a catalog addition (a new permission/role default)
doesn't necessarily come with a new migration. Unlike `provision_tenant.py`
(a brand-new schema), this is for the case a tenant migration or catalog
addition is authored after a tenant already exists — nothing else re-applies
either automatically. See `platform/service.py::upgrade_all_tenant_schemas`
and `docs/features/form_builder.md`.

Usage: ddev exec uv run python scripts/upgrade_all_tenants.py
"""

import asyncio

from vmss_api.core.database import AsyncSessionLocal
from vmss_api.platform.service import upgrade_all_tenant_schemas


async def _run() -> None:
    async with AsyncSessionLocal() as db:
        upgraded = await upgrade_all_tenant_schemas(db)

    print("Re-synced RBAC role grants and form-builder defaults for every tenant.")
    if not upgraded:
        print("Every tenant schema was already at the current migration head.")
        return

    for tenant, revision in upgraded:
        print(f"Upgraded tenant '{tenant.slug}' (schema '{tenant.schema_name}') to {revision}")


def main() -> None:
    asyncio.run(_run())


if __name__ == "__main__":
    main()

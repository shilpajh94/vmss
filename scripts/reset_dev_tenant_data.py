"""Clears every row in the default dev tenant's schema, plus the matching
global-schema rows that reference it, so `seed_dev_data.py` and
`seed_demo_workflow.py` can repopulate it from a genuinely clean slate.

Deliberately does NOT re-seed anything itself — see
`docs/features/configuration.md`'s "Resetting and re-seeding dev data"
section for the full sequence:

    ddev exec uv run python scripts/reset_dev_tenant_data.py --yes
    ddev exec uv run python scripts/seed_dev_data.py
    ddev exec uv run python scripts/seed_demo_workflow.py

Refuses to run when `settings.environment` looks like production, and
refuses to touch anything without an explicit `--yes` — this script only
ever does the one destructive thing it exists for, so it must never run to
completion by accident.

Usage: ddev exec uv run python scripts/reset_dev_tenant_data.py [--yes]
"""

import argparse
import asyncio
import sys

from sqlalchemy import text

from vmss_api.core.config import settings
from vmss_api.core.database import AsyncSessionLocal
from vmss_api.tenant.repository import TenantRepository

_GLOBAL_TABLES_REFERENCING_TENANT = (
    ("tenant_user_index", "tenant_id"),
    ("registration_device_keys", "tenant_id"),
    ("platform_audit_events", "target_tenant_id"),
)


async def _tenant_schema_tables(db, schema_name: str) -> list[str]:
    result = await db.execute(
        text(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema = :schema AND table_name != 'alembic_version'"
        ),
        {"schema": schema_name},
    )
    return [row[0] for row in result.fetchall()]


async def _run(confirmed: bool) -> None:
    if settings.environment.lower() == "production":
        print(
            f"Refusing to run: APP_ENV is {settings.environment!r}. This script truncates "
            "tenant data and must never run against a production environment.",
            file=sys.stderr,
        )
        raise SystemExit(1)

    async with AsyncSessionLocal() as db:
        tenant = await TenantRepository(db).get_by_slug(settings.default_tenant_slug)
        if tenant is None:
            print(
                f"No tenant with slug {settings.default_tenant_slug!r} — nothing to reset. "
                "Run `ddev exec uv run python scripts/seed_dev_data.py` first.",
                file=sys.stderr,
            )
            raise SystemExit(1)

        tables = await _tenant_schema_tables(db, tenant.schema_name)

        print(
            f"About to clear {len(tables)} tables in schema {tenant.schema_name!r} "
            f"(tenant {tenant.slug!r}, id {tenant.id}), plus this tenant's rows in "
            f"{', '.join(f'global.{t}' for t, _ in _GLOBAL_TABLES_REFERENCING_TENANT)}."
        )
        if not confirmed:
            print("Re-run with --yes to actually clear this data. Nothing was touched.")
            raise SystemExit(1)

        if tables:
            quoted = ", ".join(f'"{tenant.schema_name}"."{t}"' for t in tables)
            await db.execute(text(f"TRUNCATE TABLE {quoted} CASCADE"))
        for table, column in _GLOBAL_TABLES_REFERENCING_TENANT:
            await db.execute(
                text(f"DELETE FROM global.{table} WHERE {column} = :tenant_id"),
                {"tenant_id": tenant.id},
            )
        await db.commit()

    print(
        f"Cleared tenant {tenant.slug!r} (schema {tenant.schema_name!r}). Next: "
        "`ddev exec uv run python scripts/seed_dev_data.py`, then "
        "`ddev exec uv run python scripts/seed_demo_workflow.py`."
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--yes", action="store_true", help="Actually perform the clear (otherwise dry-run only)."
    )
    args = parser.parse_args()
    asyncio.run(_run(args.yes))


if __name__ == "__main__":
    main()

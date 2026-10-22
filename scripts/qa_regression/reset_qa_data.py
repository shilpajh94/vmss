"""Deletes QA-created invitations (primary contact named `QA ...`, which
covers the API runner's `QA Visitor ...`/`QA Probe ...`, the browser
suite's `QA E2E ...` and the load test's `QA LOAD ...`) plus their child
rows, from the local default tenant only.

Scoped by name prefix, never a blanket delete: the default tenant is also
the admin's manual-QA tenant. Audit logs are left alone — they're
append-only by design (security-architecture.md §5).

Usage: ddev exec uv run python scripts/qa_regression/reset_qa_data.py [--yes]
"""

import argparse
import asyncio
import sys

from sqlalchemy import text

from vmss_api.core.config import settings
from vmss_api.core.database import AsyncSessionLocal, engine
from vmss_api.tenant.repository import TenantRepository

QA_NAME_PATTERN = "QA %"
_CHILD_TABLES = (
    "invitation_approval_steps",
    "invitation_qr_codes",
    "invitation_vehicles",
    "invitation_visitors",
)


async def reset(confirmed: bool) -> None:
    if settings.environment.lower() == "production":
        print("Refusing to run in production.", file=sys.stderr)
        raise SystemExit(2)
    try:
        async with AsyncSessionLocal() as db:
            tenant = await TenantRepository(db).get_by_slug(settings.default_tenant_slug)
            if tenant is None:
                raise SystemExit("No default tenant.")
            schema = tenant.schema_name
            qa_ids = (
                f'SELECT id FROM "{schema}".invitations WHERE primary_contact_full_name LIKE :p'
            )
            count = (
                await db.execute(text(f"SELECT count(*) FROM ({qa_ids}) q"), {"p": QA_NAME_PATTERN})
            ).scalar_one()
            if not confirmed:
                print(f"{count} QA invitations in {schema} would be deleted. Re-run with --yes.")
                return
            for table in _CHILD_TABLES:
                await db.execute(
                    text(f'DELETE FROM "{schema}".{table} WHERE invitation_id IN ({qa_ids})'),
                    {"p": QA_NAME_PATTERN},
                )
            await db.execute(
                text(f'DELETE FROM "{schema}".invitations WHERE primary_contact_full_name LIKE :p'),
                {"p": QA_NAME_PATTERN},
            )
            await db.commit()
            print(f'Deleted {count} QA invitations (and their child rows) from "{schema}".')
    finally:
        await engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--yes", action="store_true")
    args = parser.parse_args()
    asyncio.run(reset(args.yes))


if __name__ == "__main__":
    main()

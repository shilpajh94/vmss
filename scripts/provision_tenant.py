"""Provisions a new tenant from the command line — creates its Postgres
schema, runs every tenant migration against it, and records it in the global
`tenants` registry. The same flow `POST /api/v1/platform/tenants` runs; this
is the ops-facing equivalent for when a superadmin API caller isn't
convenient. See `platform/service.py::create_tenant` and
`docs/features/platform.md`.

Usage: ddev exec uv run python scripts/provision_tenant.py --name "Acme Inc" --slug acme
"""

import argparse
import asyncio

from vmss_api.core.database import AsyncSessionLocal
from vmss_api.platform.service import create_tenant


async def _run(name: str, slug: str) -> None:
    async with AsyncSessionLocal() as db:
        tenant = await create_tenant(db, name=name, slug=slug)
        print(f"Provisioned tenant '{tenant.slug}' (schema '{tenant.schema_name}')")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--name", required=True, help="Display name, e.g. 'Acme Inc'")
    parser.add_argument("--slug", required=True, help="URL-safe slug, e.g. 'acme' (a-z0-9-)")
    args = parser.parse_args()
    asyncio.run(_run(args.name, args.slug))


if __name__ == "__main__":
    main()

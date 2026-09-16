"""Waits for Postgres to accept connections before `scripts/prestart.sh`
runs migrations — the DB container can still be starting up when the API
container's entrypoint fires. A plain retry loop, not a new dependency
(`tenacity`, which the upstream fastapi/full-stack-fastapi-template uses for
this): nothing else in this project needs it, and this is the only caller.

Also home to the tenant-schema-drift check `scripts/prestart.sh` runs *after*
the global migration (once `tenant_schema_versions` is guaranteed to exist),
warning if a tenant's schema wasn't caught up when a new `alembic_tenant`
migration shipped — see `platform/service.py::find_tenants_behind_head`.

Usage: python -m vmss_api.backend_pre_start [--check-tenant-drift]
"""

import argparse
import asyncio

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from vmss_api.core.config import settings
from vmss_api.core.database import AsyncSessionLocal
from vmss_api.core.logging import configure_logging, logger

_MAX_ATTEMPTS = 30
_DELAY_SECONDS = 2


async def wait_for_db() -> None:
    engine = create_async_engine(settings.database_url)
    try:
        for attempt in range(1, _MAX_ATTEMPTS + 1):
            try:
                async with engine.connect() as conn:
                    await conn.execute(text("SELECT 1"))
                logger.info("database_ready", attempt=attempt)
                return
            except Exception as exc:  # noqa: BLE001 — deliberately broad: any connect failure means "retry"
                logger.warning("database_not_ready", attempt=attempt, error=str(exc))
                if attempt == _MAX_ATTEMPTS:
                    raise
                await asyncio.sleep(_DELAY_SECONDS)
    finally:
        await engine.dispose()


async def check_tenant_schema_drift() -> None:
    """Logs a `WARNING` per tenant whose schema is behind the current
    `alembic_tenant` migration head, per `logging-observability.md` §3 —
    deliberately a warning, not a hard failure: an existing tenant lagging a
    migration doesn't mean the *global* schema/app can't start, only that
    that tenant's own feature surface may error until someone runs
    `scripts/upgrade_all_tenants.py`.

    A migration tree with more than one head is a distinct, higher-severity
    condition — it blocks *every* tenant from being upgradable, not just
    one lagging tenant — so it's logged at `ERROR` instead. Caught here
    explicitly (rather than left to propagate) so `scripts/prestart.sh`'s
    `set -euo pipefail` doesn't turn this into an unhandled crash that
    blocks startup entirely, which would defeat the point of this check
    being a non-blocking warning.
    """
    from vmss_api.platform.service import (
        TenantMigrationHeadsAmbiguousError,
        find_tenants_behind_head,
    )

    async with AsyncSessionLocal() as db:
        try:
            lagging = await find_tenants_behind_head(db)
        except TenantMigrationHeadsAmbiguousError as exc:
            logger.error("tenant_migration_heads_ambiguous", heads=exc.heads)
            return

    if not lagging:
        logger.info("tenant_schema_drift_check_clean")
        return

    for tenant in lagging:
        logger.warning(
            "tenant_schema_behind_head",
            tenant_id=str(tenant.id),
            slug=tenant.slug,
            schema=tenant.schema_name,
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check-tenant-drift",
        action="store_true",
        help="Run the tenant-schema-drift check instead of waiting for Postgres.",
    )
    args = parser.parse_args()

    configure_logging(settings.debug, settings.log_level)
    if args.check_tenant_drift:
        asyncio.run(check_tenant_schema_drift())
    else:
        asyncio.run(wait_for_db())

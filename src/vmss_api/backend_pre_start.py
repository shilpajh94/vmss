"""Waits for Postgres to accept connections before `scripts/prestart.sh`
runs migrations — the DB container can still be starting up when the API
container's entrypoint fires. A plain retry loop, not a new dependency
(`tenacity`, which the upstream fastapi/full-stack-fastapi-template uses for
this): nothing else in this project needs it, and this is the only caller.

Usage: python -m vmss_api.backend_pre_start
"""

import asyncio

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from vmss_api.core.config import settings
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


if __name__ == "__main__":
    configure_logging(settings.debug)
    asyncio.run(wait_for_db())

"""Removes every tenant except the default one (`TENANT_DEFAULT_SLUG`) from a
local or testing environment — the tenant's schema, its rows in the global
tables that reference it, its `tenants` registry row, its Redis keys, and
its local storage folder — plus any Redis keys and storage folders left
under tenant ids that have no `tenants` row at all (e.g. from test runs).
The default tenant and its data are never touched. See
`docs/features/configuration.md`'s "One tenant locally".

Run it after any experiment that created an extra tenant, then
`scripts/upgrade_all_tenants.py` so the remaining tenant is at head:

    ddev exec uv run python scripts/prune_non_default_tenants.py          # dry run
    ddev exec uv run python scripts/prune_non_default_tenants.py --yes
    ddev exec uv run python scripts/upgrade_all_tenants.py

Refuses unless `APP_ENV` is local/test/testing, refuses if the default
tenant doesn't exist (that would mean "delete every tenant"), and without
`--yes` only prints what it would remove. Database removals are one
transaction; Redis keys and files are cleaned only after it commits.

Usage: ddev exec uv run python scripts/prune_non_default_tenants.py [--yes]
"""

import argparse
import asyncio
import re
import shutil
import sys
import uuid
from dataclasses import dataclass, field
from pathlib import Path

from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from vmss_api.core.config import settings
from vmss_api.core.database import AsyncSessionLocal
from vmss_api.core.redis import get_redis

ALLOWED_ENVIRONMENTS = ("local", "test", "testing")
_GLOBAL = settings.global_schema_name

# Every global-schema table with a column pointing at a tenant. Deleted
# before the `tenants` row itself.
GLOBAL_TABLES_REFERENCING_TENANT = (
    ("tenant_user_index", "tenant_id"),
    ("tenant_schema_versions", "tenant_id"),
    ("registration_device_keys", "tenant_id"),
    ("platform_audit_events", "target_tenant_id"),
)


class PruneRefusedError(Exception):
    pass


@dataclass
class TenantRemoval:
    tenant_id: uuid.UUID
    slug: str
    schema_name: str
    drop_schema: bool
    global_rows: dict[str, int] = field(default_factory=dict)
    redis_keys: int = 0
    storage_path: Path | None = None
    storage_files: int = 0


@dataclass
class PruneResult:
    tenants: list[TenantRemoval] = field(default_factory=list)
    # Leftovers filed under a tenant id with no `tenants` row (e.g. from test
    # runs sharing this storage root and Redis) — see design.md Decision 7.
    orphan_dirs: list[Path] = field(default_factory=list)
    orphan_redis_keys: list[str] = field(default_factory=list)

    @property
    def is_empty(self) -> bool:
        return not (self.tenants or self.orphan_dirs or self.orphan_redis_keys)


def _tenant_id_segment(name: str) -> uuid.UUID | None:
    try:
        return uuid.UUID(name)
    except ValueError:
        return None


async def _orphan_redis_keys(redis: Redis, registered: set[uuid.UUID]) -> list[str]:
    orphans = []
    async for key in redis.scan_iter(match="vmss:*", count=500):
        parts = key.split(":", 2)
        tenant_id = _tenant_id_segment(parts[1]) if len(parts) > 2 else None
        if tenant_id is not None and tenant_id not in registered:
            orphans.append(key)
    return orphans


def _orphan_dirs(storage_root: Path, registered: set[uuid.UUID]) -> list[Path]:
    if settings.storage_backend != "local":
        return []
    root = storage_root.resolve()
    base = root / "vmss"
    if not base.is_dir():
        return []
    orphans = []
    for entry in base.iterdir():
        tenant_id = _tenant_id_segment(entry.name)
        if (
            tenant_id is not None
            and tenant_id not in registered
            and entry.is_dir()
            and not entry.is_symlink()
            and entry.resolve().is_relative_to(root)
        ):
            orphans.append(entry)
    return sorted(orphans)


def _schema_is_safe(schema_name: str) -> bool:
    # Slugs are `[a-z0-9-]`, so hyphens are legitimate; nothing that could
    # close the quoted identifier in `DROP SCHEMA "..."` gets through.
    return (
        re.fullmatch(rf"{re.escape(settings.tenant_schema_prefix)}[a-z0-9_-]+", schema_name)
        is not None
    )


def _storage_dir(storage_root: Path, tenant_id: uuid.UUID) -> Path | None:
    if settings.storage_backend != "local":
        return None
    root = storage_root.resolve()
    path = (root / "vmss" / str(tenant_id)).resolve()
    return path if path.is_relative_to(root) and path != root else None


async def _redis_keys(redis: Redis, tenant_id: uuid.UUID) -> list[str]:
    return [key async for key in redis.scan_iter(match=f"vmss:{tenant_id}:*", count=500)]


async def prune_non_default_tenants(
    db: AsyncSession,
    redis: Redis,
    storage_root: Path,
    *,
    environment: str,
    default_slug: str,
    confirmed: bool,
) -> PruneResult:
    """Returns what was removed (or, unconfirmed, what would be). Raises
    `PruneRefusedError` before touching anything if a guard fails.
    """
    if environment.lower() not in ALLOWED_ENVIRONMENTS:
        raise PruneRefusedError(
            f"APP_ENV is {environment!r}; this only runs in {', '.join(ALLOWED_ENVIRONMENTS)}."
        )
    rows = (await db.execute(text(f'SELECT id, slug, schema_name FROM "{_GLOBAL}".tenants'))).all()
    default = next((row for row in rows if row.slug == default_slug), None)
    if default is None:
        raise PruneRefusedError(
            f"No tenant with slug {default_slug!r}; refusing, since that would remove every tenant."
        )

    removals: list[TenantRemoval] = []
    for row in rows:
        if row.id == default.id or row.schema_name == default.schema_name:
            continue
        removal = TenantRemoval(
            tenant_id=row.id,
            slug=row.slug,
            schema_name=row.schema_name,
            drop_schema=_schema_is_safe(row.schema_name),
        )
        for table, column in GLOBAL_TABLES_REFERENCING_TENANT:
            removal.global_rows[table] = (
                await db.execute(
                    text(f'SELECT count(*) FROM "{_GLOBAL}".{table} WHERE {column} = :tenant_id'),
                    {"tenant_id": row.id},
                )
            ).scalar_one()
        removal.redis_keys = len(await _redis_keys(redis, row.id))
        removal.storage_path = _storage_dir(storage_root, row.id)
        if removal.storage_path is not None and removal.storage_path.is_dir():
            removal.storage_files = sum(1 for p in removal.storage_path.rglob("*") if p.is_file())
        removals.append(removal)

    # Every tenant id with a `tenants` row right now — including the ones
    # being removed, whose data is already accounted for above.
    registered = {row.id for row in rows}
    result = PruneResult(
        tenants=removals,
        orphan_dirs=_orphan_dirs(storage_root, registered),
        orphan_redis_keys=await _orphan_redis_keys(redis, registered),
    )
    if not confirmed or result.is_empty:
        return result

    try:
        for removal in removals:
            if removal.drop_schema:
                await db.execute(text(f'DROP SCHEMA IF EXISTS "{removal.schema_name}" CASCADE'))
            for table, column in GLOBAL_TABLES_REFERENCING_TENANT:
                await db.execute(
                    text(f'DELETE FROM "{_GLOBAL}".{table} WHERE {column} = :tenant_id'),
                    {"tenant_id": removal.tenant_id},
                )
            await db.execute(
                text(f'DELETE FROM "{_GLOBAL}".tenants WHERE id = :tenant_id'),
                {"tenant_id": removal.tenant_id},
            )
        await db.commit()
    except Exception:
        await db.rollback()
        raise

    # Only after the commit: a crash here leaves harmless orphaned cache
    # entries/files, never a database row pointing at a dropped schema.
    for removal in removals:
        keys = await _redis_keys(redis, removal.tenant_id)
        if keys:
            await redis.delete(*keys)
        if removal.storage_path is not None and removal.storage_path.is_dir():
            shutil.rmtree(removal.storage_path)
    if result.orphan_redis_keys:
        await redis.delete(*result.orphan_redis_keys)
    for path in result.orphan_dirs:
        shutil.rmtree(path)
    return result


def _describe(removal: TenantRemoval) -> str:
    rows = ", ".join(f"{table}={count}" for table, count in removal.global_rows.items())
    schema = (
        removal.schema_name
        if removal.drop_schema
        else f"{removal.schema_name} (unsafe name — NOT dropped)"
    )
    storage = (
        f"{removal.storage_path} ({removal.storage_files} files)"
        if removal.storage_path is not None
        else "skipped (non-local storage backend)"
    )
    return (
        f"- tenant {removal.slug!r} (id {removal.tenant_id})\n"
        f"    schema: {schema}\n"
        f"    global rows: {rows}\n"
        f"    redis keys: {removal.redis_keys}\n"
        f"    storage: {storage}"
    )


async def _run(confirmed: bool) -> None:
    async with AsyncSessionLocal() as db:
        try:
            result = await prune_non_default_tenants(
                db,
                await get_redis(),
                Path(settings.storage_root),
                environment=settings.environment,
                default_slug=settings.default_tenant_slug,
                confirmed=confirmed,
            )
        except PruneRefusedError as exc:
            print(f"Refusing to run: {exc}", file=sys.stderr)
            raise SystemExit(1) from exc

    if result.is_empty:
        print(
            f"Only the default tenant {settings.default_tenant_slug!r} exists and nothing is "
            "left behind by other tenant ids — nothing to remove."
        )
        return
    verb = "Removed" if confirmed else "Would remove"
    print(f"{verb} {len(result.tenants)} tenant(s), keeping {settings.default_tenant_slug!r}:")
    for removal in result.tenants:
        print(_describe(removal))
    print(
        f"{verb} leftovers under unregistered tenant ids: {len(result.orphan_dirs)} storage "
        f"folder(s), {len(result.orphan_redis_keys)} Redis key(s)."
    )
    if not confirmed:
        print("Re-run with --yes to actually remove them. Nothing was touched.")
        raise SystemExit(1)
    print("Next: `ddev exec uv run python scripts/upgrade_all_tenants.py`.")


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--yes", action="store_true", help="Actually remove the tenants (otherwise dry-run only)."
    )
    args = parser.parse_args()
    asyncio.run(_run(args.yes))


if __name__ == "__main__":
    main()

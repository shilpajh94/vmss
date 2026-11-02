"""`scripts/prune_non_default_tenants.py` (prune-local-to-default-tenant):
every non-default tenant's schema, global rows, registry row, Redis keys
and local files go; the default tenant's are untouched. Loaded by path, the
same way the migration tests load their revision files.
"""

import importlib.util
import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from pathlib import Path

import pytest
import pytest_asyncio
from redis.asyncio import Redis, from_url
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from factories import BranchFactory, TenantFactory
from vmss_api.core.config import settings
from vmss_api.org_structure.models import Branch
from vmss_api.platform.models import TenantSchemaVersion, TenantUserIndex
from vmss_api.tenant.models import Tenant

_SCRIPT = Path(__file__).parents[1] / "scripts/prune_non_default_tenants.py"
_OTHER_SCHEMA = "tenant_prune-other_test"  # hyphenated, like a real slug can be


def _load_script():
    spec = importlib.util.spec_from_file_location("prune_non_default_tenants", _SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


prune = _load_script()


@pytest_asyncio.fixture
async def other_tenant(
    db_session: AsyncSession, make_tenant_schema, open_tenant_session, tenant: Tenant
) -> Tenant:
    """A second tenant with a real schema, a branch in it, and a row in each
    global table that references a tenant.
    """
    await make_tenant_schema(_OTHER_SCHEMA)
    other = TenantFactory.build(
        id=uuid.uuid4(), slug="prune-other", schema_name=_OTHER_SCHEMA, timezone="UTC"
    )
    db_session.add(other)
    await db_session.flush()
    db_session.add_all(
        [
            TenantUserIndex(
                email="someone@prune-other.example", tenant_id=other.id, user_id=uuid.uuid4()
            ),
            TenantSchemaVersion(tenant_id=other.id, revision="head", applied_at=datetime.now(UTC)),
        ]
    )
    await db_session.commit()
    async with open_tenant_session(_OTHER_SCHEMA) as other_session:
        other_session.add(BranchFactory.build(id=uuid.uuid4(), name="Other", code="OTH"))
        await other_session.commit()
    return other


@pytest_asyncio.fixture
async def redis() -> AsyncIterator[Redis]:
    """The suite-wide test cache database (conftest pins it to db 15), never
    the dev one: orphan cleanup deletes every `vmss:<uuid>:*` key whose
    tenant isn't registered in the *test* DB. A client of its own rather than
    `get_redis()`'s shared one, whose pooled connections can't cross the
    per-test event loops.
    """
    client = from_url(settings.redis_url, decode_responses=True)
    await client.flushdb()
    yield client
    await client.flushdb()
    await client.aclose()


async def _schema_exists(db: AsyncSession, schema: str) -> bool:
    return bool(
        await db.scalar(
            text("SELECT count(*) FROM information_schema.schemata WHERE schema_name = :s"),
            {"s": schema},
        )
    )


async def _run(db: AsyncSession, redis: Redis, storage_root: Path, **overrides):
    kwargs = {"environment": "local", "default_slug": "acme-test", "confirmed": True}
    kwargs.update(overrides)
    return await prune.prune_non_default_tenants(db, redis, storage_root, **kwargs)


async def test_prune_removes_other_tenant_and_keeps_default(
    db_session: AsyncSession,
    tenant: Tenant,
    other_tenant: Tenant,
    redis: Redis,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(prune.settings, "storage_backend", "local")
    default_id, other_id = tenant.id, other_tenant.id
    db_session.add(BranchFactory.build(id=uuid.uuid4(), name="Main", code="MAIN"))
    db_session.add(
        TenantUserIndex(email="admin@acme-test.example", tenant_id=default_id, user_id=uuid.uuid4())
    )
    await db_session.commit()
    keep_key, drop_key = f"vmss:{default_id}:test:keep", f"vmss:{other_id}:test:drop"
    await redis.set(keep_key, "1")
    await redis.set(drop_key, "1")
    for tenant_id in (default_id, other_id):
        folder = tmp_path / "vmss" / str(tenant_id)
        folder.mkdir(parents=True)
        (folder / "photo.jpg").write_bytes(b"x")

    result = await _run(db_session, redis, tmp_path)

    [removal] = result.tenants
    assert (removal.slug, removal.drop_schema) == ("prune-other", True)
    assert removal.global_rows["tenant_user_index"] == 1
    assert removal.global_rows["tenant_schema_versions"] == 1
    assert (removal.redis_keys, removal.storage_files) == (1, 1)
    # The removed tenant's data isn't double-counted as orphaned.
    assert (result.orphan_dirs, result.orphan_redis_keys) == ([], [])

    assert not await _schema_exists(db_session, _OTHER_SCHEMA)
    assert await db_session.scalar(select(func.count()).select_from(Tenant)) == 1
    assert (
        await db_session.scalar(
            select(func.count())
            .select_from(TenantUserIndex)
            .where(TenantUserIndex.tenant_id == other_id)
        )
        == 0
    )
    assert (
        await db_session.scalar(
            select(func.count())
            .select_from(TenantSchemaVersion)
            .where(TenantSchemaVersion.tenant_id == other_id)
        )
        == 0
    )
    assert await redis.exists(drop_key) == 0
    assert not (tmp_path / "vmss" / str(other_id)).exists()

    # The default tenant is untouched.
    assert await _schema_exists(db_session, tenant.schema_name)
    assert await db_session.scalar(select(func.count()).select_from(Branch)) == 1
    assert (
        await db_session.scalar(
            select(func.count())
            .select_from(TenantUserIndex)
            .where(TenantUserIndex.tenant_id == default_id)
        )
        == 1
    )
    assert await redis.exists(keep_key) == 1
    assert (tmp_path / "vmss" / str(default_id) / "photo.jpg").exists()


async def _seed_orphans(redis: Redis, tmp_path: Path, default_id: uuid.UUID) -> dict[str, object]:
    orphan_id = uuid.uuid4()
    entries: dict[str, object] = {
        "orphan_key": f"vmss:{orphan_id}:invitations:idempotency:abc",
        "default_key": f"vmss:{default_id}:reports:snapshot",
        "non_tenant_key": "vmss:not-a-tenant:something",
        "orphan_dir": tmp_path / "vmss" / str(orphan_id),
        "default_dir": tmp_path / "vmss" / str(default_id),
        "non_tenant_dir": tmp_path / "vmss" / "shared-assets",
    }
    for key in ("orphan_key", "default_key", "non_tenant_key"):
        await redis.set(str(entries[key]), "1")
    for key in ("orphan_dir", "default_dir", "non_tenant_dir"):
        folder = entries[key]
        assert isinstance(folder, Path)
        (folder / "invitations").mkdir(parents=True)
        (folder / "invitations" / "file.jpg").write_bytes(b"x")
    return entries


async def test_prune_removes_orphaned_leftovers_only(
    db_session: AsyncSession,
    tenant: Tenant,
    redis: Redis,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(prune.settings, "storage_backend", "local")
    entries = await _seed_orphans(redis, tmp_path, tenant.id)

    result = await _run(db_session, redis, tmp_path)

    assert result.tenants == []
    assert result.orphan_dirs == [entries["orphan_dir"]]
    assert result.orphan_redis_keys == [entries["orphan_key"]]
    assert not Path(str(entries["orphan_dir"])).exists()
    assert await redis.exists(str(entries["orphan_key"])) == 0
    for kept in ("default_dir", "non_tenant_dir"):
        assert Path(str(entries[kept])).exists(), kept
    for kept in ("default_key", "non_tenant_key"):
        assert await redis.exists(str(entries[kept])) == 1, kept


async def test_prune_dry_run_changes_nothing(
    db_session: AsyncSession,
    tenant: Tenant,
    other_tenant: Tenant,
    redis: Redis,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(prune.settings, "storage_backend", "local")
    entries = await _seed_orphans(redis, tmp_path, tenant.id)

    result = await _run(db_session, redis, tmp_path, confirmed=False)

    assert [removal.slug for removal in result.tenants] == ["prune-other"]
    assert (len(result.orphan_dirs), len(result.orphan_redis_keys)) == (1, 1)
    assert await _schema_exists(db_session, _OTHER_SCHEMA)
    assert await db_session.scalar(select(func.count()).select_from(Tenant)) == 2
    assert await db_session.scalar(text(f'SELECT count(*) FROM "{_OTHER_SCHEMA}".branches')) == 1
    assert Path(str(entries["orphan_dir"])).exists()
    assert await redis.exists(str(entries["orphan_key"])) == 1


@pytest.mark.parametrize("environment", ["production", "staging"])
async def test_prune_refuses_outside_local_and_testing(
    db_session: AsyncSession,
    tenant: Tenant,
    other_tenant: Tenant,
    redis: Redis,
    tmp_path: Path,
    environment: str,
) -> None:
    with pytest.raises(prune.PruneRefusedError):
        await _run(db_session, redis, tmp_path, environment=environment)
    assert await _schema_exists(db_session, _OTHER_SCHEMA)
    assert await db_session.scalar(select(func.count()).select_from(Tenant)) == 2


async def test_prune_refuses_when_default_tenant_missing(
    db_session: AsyncSession, tenant: Tenant, other_tenant: Tenant, redis: Redis, tmp_path: Path
) -> None:
    with pytest.raises(prune.PruneRefusedError):
        await _run(db_session, redis, tmp_path, default_slug="no-such-tenant")
    assert await _schema_exists(db_session, _OTHER_SCHEMA)
    assert await db_session.scalar(select(func.count()).select_from(Tenant)) == 2


async def test_prune_with_only_default_tenant_removes_nothing(
    db_session: AsyncSession, tenant: Tenant, redis: Redis, tmp_path: Path
) -> None:
    result = await _run(db_session, redis, tmp_path)
    assert result.is_empty
    assert await _schema_exists(db_session, tenant.schema_name)
    assert await db_session.scalar(select(func.count()).select_from(Tenant)) == 1

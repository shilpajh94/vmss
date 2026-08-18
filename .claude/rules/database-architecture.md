---
trigger: always_on
---

# Database Architectural Standards — VMSS_API

Adapted from the reference `database-architecture.md` (Peace Observatory Backend),
which was file/CSV + optional-SQL-later oriented. VMSS_API is PostgreSQL-first from
day one — the visitor lifecycle (registration, approvals, check-in/out, audit) is
inherently relational and transactional, so there's no file-based data tier here.

## 1. Data Source Strategy

- **Relational data (all domain data)**: PostgreSQL 17 via SQLAlchemy 2.0 (async)
  + `asyncpg`. This is the system of record — visitors, invitations, approvals,
  check-in/out events, audit logs, admin config.
- **Cache / ephemeral state**: Redis — config lookups, OTP codes, rate-limit
  counters, Celery broker/result backend.
- **File storage**: visitor photos, ID scans, uploaded documents — local disk in
  dev, S3-compatible object storage in prod, behind one storage interface so the
  swap is a config change, not a code change.

## 2. Tenancy — schema-per-tenant

**Revision of an earlier decision.** This project originally shipped
shared-schema, column-based tenancy (`organization_id` on every table). It has
been rebuilt on **schema-per-tenant**: one dedicated Postgres schema per
tenant, plus a **global schema** for cross-tenant registry tables. This is a
stronger isolation guarantee than a WHERE-clause discipline can ever be — a
repository bug can't leak one tenant's rows into another's result set when
there's no shared table to leak from in the first place. The tradeoff (real:
provisioning, dual migrations, cross-schema FKs) is accepted for that reason.

| Tier | Schema | Contents | Reachable from |
|---|---|---|---|
| Global | `global` (`settings.global_schema_name`) | `tenants` (registry), `superadmins`, `permissions` (catalog — identical across tenants), `tenant_user_index` (auth routing), `tenant_schema_versions`, `platform_audit_events` | Any session, always — these tables carry an explicit `schema="global"`. |
| Per-tenant | `tenant_<slug>` (`settings.tenant_schema_prefix`) | `users`, `roles`, `role_permissions`, `user_roles`, `audit_logs`, and every future domain table (visitors, invitations, check-ins, ...) | Only a session bound to that schema via `schema_translate_map` (below). |

```python
# src/vmss_api/core/database.py
class Base(DeclarativeBase):
    """Tenant-scoped tables. No explicit schema — resolved per-connection."""


class GlobalBase(DeclarativeBase):
    """Cross-tenant registry tables. Explicit schema, reachable from anywhere."""

    metadata = MetaData(schema=settings.global_schema_name)
```

A tenant table (`Base` subclass) is defined with **no schema in its table
object** — which physical schema it resolves against is decided per
connection, using SQLAlchemy's `schema_translate_map`:

```python
# src/vmss_api/core/database.py
async def get_tenant_session(schema_name: str):
    async with AsyncSession(
        engine.execution_options(schema_translate_map={None: schema_name})
    ) as session:
        yield session
```

A session built from the plain `engine`/`get_db` (no translate map) simply
can't resolve tenant tables at all — that's intentional, not an oversight. It
forces every tenant-table query through a tenant-bound session.

### Request-time resolution order

Loading the user first and reading `user.organization_id` off it — the old
flow — doesn't work here: querying `users` requires already knowing the
schema. The dependency chain in `core/tenancy.py` runs in the opposite order,
each step composable via `Depends()`:

```
decode_token(bearer)                    # JWT claims only — no DB
  → get_tenant(tenant_id)                # global `tenants` lookup, 404/403 if inactive
    → get_tenant_db(tenant)               # session bound to tenant.schema_name
      → get_current_user(sub, tenant_db)   # NOW `users` resolves against the right schema
        → require_permission(code)
```

`tenant_id` is a JWT claim (not a column read post-load) precisely so this
ordering is possible.

### The auth-routing problem, and `tenant_user_index`

Login receives only an email/password — nothing that says which schema to
query. `tenant_user_index` (global schema, `platform/models.py`) is the fix:
`email → tenant_id, user_id`. It's the first hop of every login
(`auth/service.py::authenticate_user`), and is written in the **same
transaction** as every `User` row creation (`auth/service.py::create_user`) —
global and tenant tables coexist on one connection, so that's one atomic
commit, not a distributed write to keep in sync by hand. One consequence:
**an email can only belong to one tenant** in this design (the index's
primary key is the email). Revisit if a cross-tenant-membership use case
shows up.

### Cross-schema references

`permissions` (the catalog of *what actions exist*) is global — identical for
every tenant, only which roles grant them is tenant-specific. Tenant-scoped
join tables reference it with a schema-qualified FK, which Postgres supports
natively within one database:

```python
Column("permission_id", Uuid, ForeignKey(f"{settings.global_schema_name}.permissions.id"))
```

- Today, exactly one row exists in `tenants`. Do not write code that hardcodes
  its id or assumes it's the only one — always resolve it through
  `get_tenant`/`get_tenant_db` (`core/tenancy.py`).

## 3. Data Access — Repository Pattern (mandatory)

- Every feature that owns tables has a `repository.py`. It is the **only** place
  that imports `AsyncSession` — routers and services never construct queries
  directly.
- Tenant-scoped repositories inherit `TenantScopedRepository`. Isolation is
  now structural (which schema the session it's given is bound to), not a
  WHERE clause — the base class's only remaining job is the soft-delete
  filter:

  ```python
  # src/vmss_api/core/database.py
  class TenantScopedRepository[ModelT: _SoftDeletableModel]:
      def __init__(self, session: AsyncSession) -> None:
          self.session = session  # already bound to one tenant's schema

      async def get(self, id_: uuid.UUID) -> ModelT | None:
          stmt = select(self.model).where(self.model.id == id_, self.model.deleted_at.is_(None))
          return (await self.session.execute(stmt)).scalar_one_or_none()
  ```

  A repository that builds its own session/engine instead of using the
  tenant-bound one it's given is a bug, not a style choice — it's how a query
  could silently resolve against no schema (and fail) or the wrong one.
- Global-schema repositories (`TenantRepository`, `SuperAdminRepository`, ...)
  are plain classes taking a `get_db`-sourced session — not
  `TenantScopedRepository` subclasses, since there's no tenant schema to bind
  for a registry table. Don't "fix" that by making them one.
- **DB sessions**: use `get_db` (global) or `get_tenant_db` (tenant-bound) —
  both in `core/tenancy.py`/`core/deps.py` — everywhere. Never instantiate an
  engine or session inside a service or router.

## 4. Modeling Standards

### SQLAlchemy Models (`models.py`)
- Declarative, `Mapped[...]`/`mapped_column(...)` style (SQLAlchemy 2.0), not the
  legacy `Column(...)` style.
- Every table includes `TimestampMixin` (`created_at`, `updated_at`, both
  server-side defaults), except genuinely append-only tables (`AuditLog`,
  `PlatformAuditEvent`) which only need `created_at` — rows there are never
  updated or soft-deleted.
- Inherit `Base` for a tenant-scoped table, `GlobalBase` for a cross-tenant
  registry table (§2). There's no mixin to add for tenancy anymore — which
  `Base` a model inherits *is* the tenancy declaration.
- **Soft delete, not hard delete**, for anything with compliance/audit relevance
  (visitors, visits, audit logs, blacklist entries): a nullable `deleted_at`
  column, filtered out by default in repository queries. Hard `DELETE` is reserved
  for genuinely disposable data (e.g. an expired OTP code).
- Naming: snake_case tables and columns, plural table names (`visitors`, not
  `visitor`), foreign keys as `<entity>_id`.

### Pydantic Models (`schemas.py`)
- Every request/response shape is a Pydantic model extending `CamelModel`
  (`fastapi-architecture.md` §3) — never a raw dict.
- Request and response schemas are separate classes even when nearly identical
  (`VisitorCreate` vs `VisitorOut`) — don't reuse one schema for both directions;
  it's how you accidentally let a client set `created_at`.

## 5. Migrations — two Alembic environments

Schema-per-tenant needs two independent Alembic setups, not one:

| | `alembic/` | `alembic_tenant/` |
|---|---|---|
| Targets | The global schema, once. | One tenant schema at a time. |
| Config | `alembic.ini` | `alembic_tenant.ini` |
| Metadata | `GlobalBase.metadata` | `Base.metadata` |
| `version_table_schema` | `"global"` | the target tenant's schema |
| Which schema | Fixed. | `config.attributes["tenant_schema"]` (programmatic) or `-x tenant_schema=<name>` (CLI) — see `alembic_tenant/env.py`. |

- **Alembic is mandatory** for every schema change, both trees. Never hand-edit
  the schema in any environment, including local.
- Global: `ddev exec uv run alembic revision --autogenerate -m "description"`,
  then `ddev exec uv run alembic upgrade head`, same as any single-tenant app.
- Tenant: migrations are authored once (`alembic_tenant/versions/`) and applied
  to *every* tenant schema — there's no autogenerate loop per tenant. Applying
  them is `platform/service.py::create_tenant`'s job during provisioning (or a
  future "upgrade all tenants" ops task) — see `docs/features/platform.md`.
  `CREATE SCHEMA` itself is the provisioning service's job, never a migration's
  — a tenant migration assumes its target schema already exists.
- `tenant_schema_versions` (global table) caches which revision each tenant is
  on, so "what version is every tenant at" is one global-schema query instead
  of connecting into every tenant schema to check. Alembic's own per-schema
  `alembic_version` table (inside each tenant schema) is still the source of
  truth; this is a fast-lookup mirror of it, updated by the same service call.

## 6. Caching & Background Jobs

- **Redis key convention**: `vmss:{tenant_id}:{feature}:{entity}:{id}`
  (e.g. `vmss:<tenant-id>:invitations:qr:<token>`). Redis has no concept of
  Postgres schemas, so cache keys still need an explicit tenant discriminator
  even though the database itself no longer does — use the tenant's `id`
  (from `get_tenant`), not its `schema_name`.
- **Celery** handles anything that shouldn't block a request: notification
  dispatch (email/SMS/push/Teams/Slack), scheduled reports, data-retention
  purge/anonymization jobs, reminder nudges for pending approvals.

## 7. Execution Offloading

- Blocking I/O or CPU-bound work inside a request handler (large file parsing,
  image/PDF generation) must be offloaded:
  ```python
  import anyio

  badge_pdf = await anyio.to_thread.run_sync(render_badge_pdf, visitor)
  ```

## 8. Configuration

- All connection strings, credentials, and Redis/Celery URLs live in `.env` and are
  accessed exclusively through the `settings` object in
  `src/vmss_api/core/config.py` (`pydantic-settings`). Never read `os.environ`
  directly outside that one module.

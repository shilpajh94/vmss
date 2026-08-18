---
trigger: always_on
---

# FastAPI Architectural Standards — VMSS_API

Adapted from the reference `fastapi-architecture.md` (Peace Observatory Backend).
Deviations are called out with why.

## 1. Feature-Based Modularity

One top-level package: `src/vmss_api/`. Each domain feature is a subpackage of it —
not a sibling top-level package. This is the one deliberate structural change from
the reference project (which had `src/app/` and `src/<feature>/` as siblings): a
single package gives one unambiguous import path (`from vmss_api.visitors import
schemas`) everywhere — in the app, in Alembic's `env.py`, in tests — with no
`try/except ModuleNotFoundError` dual-path import hack.

- **Location**: `src/vmss_api/<feature_name>/`
  (e.g. `src/vmss_api/visitors/`, `src/vmss_api/checkin/`)
- **Required files**:
  - `__init__.py` — package marker.
  - `router.py` — `APIRouter` + route definitions.
  - `service.py` — business logic and orchestration.
  - `schemas.py` — Pydantic request/response models.
  - `models.py` — SQLAlchemy models (only if the feature owns tables).
  - `repository.py` — data access (only if the feature owns tables). See
    `database-architecture.md` §3 — routers and services never touch an
    `AsyncSession` directly.
  - `tests.py` (or a `tests/` subpackage for larger features).

## 2. Layered Responsibility

| Layer | File | Responsibility |
| :--- | :--- | :--- |
| **API** | `router.py` | Route definitions, param validation, calling services, returning `success_response`/`error_response`. |
| **Logic** | `service.py` | Business rules (e.g. approval-workflow evaluation, overstay detection), orchestration across repositories/integrations. |
| **Schema** | `schemas.py` | Request/response shapes, field constraints, camelCase JSON boundary (§3). |
| **Data** | `models.py` | SQLAlchemy table definitions, relationships, tenant/timestamp mixins. |
| **Repository** | `repository.py` | Tenant-scoped queries. The only layer allowed to import `AsyncSession`. |

Routers call services; services call repositories (and integration adapters);
repositories talk to the database. No layer skips the one below it.

## 3. Pydantic Schema Convention: snake_case in Python, camelCase over the wire

The reference project's rule made API-layer *Python identifiers* camelCase to match
frontend expectations. We don't do that — it violates PEP 8 and forces every
Python-side consumer of those names to read camelCase. Instead:

```python
# src/vmss_api/core/schemas.py
from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel


class CamelModel(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        from_attributes=True,
    )
```

Every feature's `schemas.py` extends `CamelModel`. Python code stays
`visitor.check_in_time`; the JSON the React/Flutter clients see is
`"checkInTime"`. One line of config, zero naming drift in the codebase.

## 4. Async Execution and Threading

- **Endpoints**: always `async def`.
- **DB access**: async SQLAlchemy session (`AsyncSession`) end to end — no sync
  session anywhere in the request path.
- **Blocking/CPU-bound work** (badge/QR image rendering, PDF report generation,
  parsing an uploaded ID document): offload with
  `anyio.to_thread.run_sync(fn, *args)`. If it's slow enough that the caller
  shouldn't wait on it at all (e.g. bulk report export), push it to a Celery task
  instead and return a job id.

## 5. Standardized API Responses

Every JSON endpoint (i.e. everything except a raw `FileResponse` or a `204`) uses
the wrappers from `vmss_api.core.responses`:

```python
from vmss_api.core.responses import success_response, error_response

@router.get("/{visitor_id}")
async def get_visitor(visitor_id: UUID, ...) -> JSONResponse:
    visitor = await service.get_visitor(visitor_id)
    return success_response(data=VisitorOut.model_validate(visitor))
```

No dual-import fallback is needed (see §1) — `vmss_api` is always importable as
one package once `uv sync` has run.

## 6. Dependency Injection

Centralized in `src/vmss_api/core/` — `core/deps.py` re-exports the handful
every feature's `router.py` actually needs, so a route imports one module
instead of reaching into `core.database`/`core.tenancy` separately:

- `get_db` — yields a plain, global-schema-only `AsyncSession` (`core/database.py`).
- `get_tenant` — resolves the caller's `Tenant` from the access token's
  `tenant_id` claim (`core/tenancy.py`, see `database-architecture.md` §2).
- `get_tenant_db` — yields an `AsyncSession` bound to that tenant's own
  Postgres schema via `schema_translate_map`. Every tenant-scoped repository
  call goes through this, not `get_db`.
- `get_current_user` — loads the user from the resolved tenant's schema
  (`core/tenancy.py`).
- `require_permission("visitors:checkin")` — a dependency *factory* used for RBAC
  checks (`security-architecture.md` §1), so permission strings live next to the
  route that needs them instead of scattered `if` checks.

**Sanctioned exception to "core doesn't depend on features"**: `core/tenancy.py`
imports the `User` model from `vmss_api.auth.models` and `Tenant`/`TenantRepository`
from `vmss_api.tenant`. Authentication and tenant resolution are cross-cutting
infrastructure every other feature needs, so `core` is allowed this one upward
dependency on `auth` and `tenant` — no other feature package should be imported
from `core`. (`platform/service.py` has its own, separate superadmin auth chain —
it lives in `platform/`, not `core/`, since nothing outside `platform` needs it.)

## 7. Integration

- Every feature's `router.py` exposes a module-level `router = APIRouter(prefix=...,
  tags=[...])`.
- All feature routers are aggregated once in `src/vmss_api/api.py`:
  ```python
  api_router.include_router(visitors.router.router)
  ```
- `src/vmss_api/main.py` mounts `api_router` under `/api/v1` exactly once. Don't
  `include_router` directly in `main.py` for individual features — keep that list
  in `api.py` so it's the single place that shows "every route this API exposes."

# Platform

Superadmin operations: platform login and tenant provisioning. Everything
here lives in the **global** Postgres schema (`GlobalBase`) and is
authenticated separately from tenant users — a superadmin isn't a member of
any tenant's schema. See `database-architecture.md` §2–§3.

## Endpoints

| Method | Path | Auth | Description |
|---|---|---|---|
| POST | `/api/v1/platform/auth/login` | None (public), 5/minute per IP | Returns a `platform_access` token. |
| POST | `/api/v1/platform/tenants` | Superadmin | Provisions a new tenant end to end. |
| GET | `/api/v1/platform/tenants` | Superadmin | Lists every tenant. |

## Tenant provisioning

`platform/service.py::create_tenant` is the whole flow:

1. `CREATE SCHEMA IF NOT EXISTS tenant_<slug>` (its own short-lived
   connection — see the function's docstring for why it doesn't reuse the
   app's shared pooled engine).
2. Run every migration in `alembic_tenant/` against exactly that schema
   (`anyio.to_thread.run_sync`, since Alembic's command API is sync — see
   `database-architecture.md` §7).
3. Insert the `tenants` registry row and a `tenant_schema_versions`
   bookkeeping row, in that order — deliberately *after* steps 1–2 succeed,
   so a failed provisioning run never leaves a registry row pointing at a
   schema that doesn't exist or isn't migrated. Both `CREATE SCHEMA IF NOT
   EXISTS` and re-running Alembic are safe to retry.

Also exposed as `scripts/provision_tenant.py` for ops use outside the API.

## What's here vs. what's still missing

- **Here**: superadmin auth (separate `platform_access` JWT type — see
  `platform/service.py::get_current_superadmin`, which deliberately does
  **not** share `core/tenancy.py`'s tenant-user chain), tenant provisioning,
  a bookkeeping table (`tenant_schema_versions`) for "what revision is every
  tenant on" without connecting into every tenant schema to check, and
  `platform_audit_events` (empty of writers so far) for platform-level
  actions distinct from the tenant-scoped `AuditLog` in `auth/models.py`.
- **Not yet built**: tenant deactivation/deletion, superadmin management
  (creating one requires a direct DB insert today — there's no seed script
  or endpoint for it yet), and any compensation logic for a provisioning run
  that fails between steps 1–2 above and never gets retried.
- Provisioning is **not** transactional across steps 1–2 and the same
  session's step 3 — schema creation and the tenant Alembic run happen on
  their own connections, outside the request's own DB transaction. Flagged
  as an open item, not silently under-built — see `security-architecture.md`'s
  own "flagged as an open question" items for the same kind of call.

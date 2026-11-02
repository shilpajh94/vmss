# Tenant

The tenant registry. `Tenant` (`tenant/models.py`) lives in the **global**
Postgres schema — one row per tenant, `schema_name` pointing at that tenant's
own dedicated schema (`tenant_<slug>` by default). See
`database-architecture.md` §2 for the full global/tenant-schema split.

Renamed from `organizations`: the entity this package owns *is* the tenant —
the core layer already used "tenant" terminology (`TenantScopedRepository`,
`core/tenancy.py`) before this package did.

## Endpoints

| Method | Path | Auth | Permission | Description |
|---|---|---|---|---|
| GET | `/api/v1/tenants/me` | Required | `tenants:read` | Returns the caller's own tenant, including `badgePrintFlowEnabled`. |
| PATCH | `/api/v1/tenants/me/settings` | Required | `tenants:update` | Sets `badgePrintFlowEnabled` for the caller's own tenant (audited). The badge flow is live only when this and `BADGE_PRINT_FLOW_ENABLED` are both true — see `docs/features/checkin_badge.md`. |

## Notes for whoever builds the next admin-facing tenant endpoints

- Update endpoints (renaming a tenant, deactivating it) don't exist yet —
  when added, they belong in this same feature package, following the
  `router.py → service.py → repository.py` chain. **Creating** a tenant,
  however, is not this package's job — see `docs/features/platform.md`;
  provisioning a Postgres schema and running every tenant migration against
  it is a superadmin/platform operation, not something a tenant does to
  itself.
- `TenantRepository` is intentionally **not** a `TenantScopedRepository`
  subclass — `Tenant` is the registry table itself, queried through the
  plain `get_db` session (there's no tenant schema to bind yet; resolving
  one is the point of this repository). Don't "fix" that by making it one.
- `TenantOut` deliberately excludes `schema_name` — the physical schema name
  is an internal implementation detail, not something to leak to API clients.

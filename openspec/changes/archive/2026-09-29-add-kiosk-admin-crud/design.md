## Context

Branch is the reference: tenant-scoped model in `org_structure`, thin router
with `require_permission`, service, repository extending
`TenantScopedRepository`, `_queue_audit` background audit, pagination via
`get_pagination` and `paginated_response`. Kiosk is a simpler flat entity.
`RegistrationDeviceKey` (global schema) is unrelated and untouched.

## Goals / Non-Goals

**Goals:** admin-only CRUD + hide + soft delete for a flat Kiosk record.
**Non-Goals:** device-key linkage, branch scoping, public endpoints,
walk-in flow changes.

## Decisions

1. **New feature package `src/vmss_api/kiosks/`** rather than adding to
   `org_structure`: kiosk isn't part of the Company→Desk org chart, and
   `fastapi-architecture.md` §1 prescribes one package per feature. Follows the
   required file layout; `tasks.py` not created (no async work).
2. **Model** `Kiosk(Base, TimestampMixin)`, table `kiosks`: `id` UUID, `name`
   String(255), `description` String(2000) nullable, `is_active` bool default
   true, `is_hidden` bool default false (indexed), `deleted_at` nullable. Unique
   partial index on `lower(name)` where `deleted_at IS NULL` (mirrors
   `ix_branches_code`), so deleted names are reusable.
3. **Not branch-scoped, company-wide permissions** — matches "Company-wide
   only" Branch write posture; no `X-Branch-ID` needed. Assumption, easy to add
   a nullable `branch_id` later.
4. **Permissions** `kiosks:manage` / `kiosks:view` appended to
   `PERMISSION_CODES` (Admin gets all automatically). Existing tenants need the
   permission rows and Admin role grants; handle in the tenant migration via
   idempotent insert into `global.permissions` is NOT allowed from a tenant
   migration, so use the same mechanism prior permission additions used
   (verify during implementation—see Open Questions).
5. **Endpoints** (`/api/v1/kiosks`, tag `kiosks`):
   `POST ""` 201, `GET ""` paginated, `GET /{id}`, `PUT /{id}`,
   `PATCH /{id}/visibility` body `{isHidden}`, `DELETE /{id}` 204. All
   `response_model=Envelope[KioskOut]`/`PaginatedEnvelope[KioskOut]` except
   delete.
6. **Hide semantics**: visibility flag only. List filters `is_hidden = false`
   unless `includeHidden=true`; get-by-id ignores it. Separate PATCH endpoint
   (not part of PUT) so hide is a distinct, audited action.
7. **List query**: `status` (`ActiveStatus`) filter reused from
   `org_structure.schemas`, `sortBy` Literal whitelist (`name`, `createdAt`),
   `sortOrder`; count + page via repository, no N+1 (flat table).
8. **Schemas**: `KioskCreate` (name min 1/max 255 stripped, description max
   2000), `KioskUpdate` (all optional, `exclude_unset`), `KioskVisibilityUpdate`,
   `KioskOut`; all `CamelModel`.
9. **Audit**: reuse the `_queue_audit` pattern (copy/relocate helper if it's
   private to org_structure).

## Risks / Trade-offs

- Name uniqueness is an assumption; a 409 on duplicate could surprise if
  duplicates were wanted → trivial to drop the index.
- Existing tenants require the migration applied per schema plus permission
  seeding, or Admin gets 403 until done.

## Migration Plan

Add one tenant Alembic revision creating `kiosks` (head-merge aware; see
`fix-tenant-migration-branch-drift`), apply to each tenant schema. Rollback:
downgrade drops the table.

## Open Questions

- How were prior new permission codes propagated to already-provisioned
  tenants? Confirm and mirror during implementation.

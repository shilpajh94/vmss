## Context

See proposal.md (Why) for the symptoms. Current state:

| Path | Code | Today's `expires_at` |
|---|---|---|
| Create (staff, walk-in via `registrations` → `create_invitation`, return visit) | `service.py::create_invitation` | `_end_of_visit_day_utc(date, tenant)` |
| Approve | `approve_invitation` → `repo.approve_if_submitted(expires_at=…)` | end of visit day |
| Reschedule `approved` | `reschedule_invitation` | end of new visit day |
| Reschedule `submitted` | `reschedule_invitation` passes `expires_at=None` | **unchanged (stale)** |
| Edit `preferredVisitDate` | `edit_invitation` → `repo.edit_if_eligible(**changes)` | **unchanged (stale)** |
| Staff extend | `extend_expiry` | caller's value (must be later) |
| Rows created before `9478fc5` (2026-09-28) | none | **`created_at + 168h`** |

`_end_of_visit_day_utc` resolves its zone through `_resolve_tenant_timezone`,
which reads only `Tenant.timezone` (dev: `UTC`). `Company.default_timezone`
(dev: `Asia/Kolkata`; one `Company` per tenant, via
`CompanyRepository.get_singleton()`) is never consulted. `Branch` has no
timezone column. The QR check-in "not before visit date" gate
(`check_in_by_qr_token`) computes `today_local` with the same tenant-only
resolver.

The web portal (`VMMS_WEB/.../VisitorInfoModal.tsx`) uses `formatDateTime`
to show `expiresAt` in browser-local time, so once the stored UTC value is
right the display is right. No web change is needed.

## Goals / Non-Goals

**Goals:**
- One visit-timezone resolver, shared by the expiry calculation and the
  QR visit-date gate.
- Every write to `preferred_visit_date` also writes the matching
  `expires_at`, in the same `UPDATE`.
- Correct the stale rows in each tenant schema once, without touching staff
  extensions.

**Non-Goals:**
- Per-branch timezones (would need a new `branches` column and admin UI).
- Changing the dashboard's "today" bounds (`dashboard/service.py`).
- Re-signing QR image URLs already embedded in sent emails.
- Expiry based on `preferredVisitTime` or `expectedDuration`. The whole day
  is valid by design.

## Decisions

### D1. Visit timezone = `Company.default_timezone` → `Tenant.timezone` → `UTC`

Replace `_resolve_tenant_timezone(tenant)` in `invitations/service.py` with
`async def _resolve_visit_timezone(tenant_db, tenant) -> ZoneInfo`. It
loads the singleton company, tries `company.default_timezone`, then
`tenant.timezone`, then falls back to `UTC`. Each invalid name logs
`invitations_invalid_timezone` at `WARNING` with `source=company|tenant`, per
logging-observability.md §3. `_end_of_visit_day_utc(visit_date, tz)` becomes
a pure function that takes the resolved `ZoneInfo`, which makes it easy to
unit test.

- *Why company first:* it's the setting an admin actually edits in the org
  setup screens. `Tenant.timezone` is a platform-provisioning default that
  nobody touches. In dev they already disagree (`Asia/Kolkata` vs `UTC`), and
  the company value is the one that matches what staff expect.
- *Alternative, tenant only and fix the data:* rejected. It keeps two
  timezone settings that can silently disagree.
- *Alternative, add `branches.timezone`:* rejected for now. It's a schema and
  UI change no one has asked for, and all current tenants are single-region.
  The resolver is the one place to extend if that changes.
- *Cost:* one extra indexed singleton lookup per create/approve/reschedule/
  edit/QR check-in. `create_invitation` already loads the company for the
  auto-approve setting, so pass that instance through instead of fetching it
  twice.

### D2. Recalculate expiry wherever the visit date is written

- `reschedule_invitation`: always pass
  `expires_at=_end_of_visit_day_utc(new_date, tz)`, not only when `approved`.
  `reschedule_if_eligible` already accepts `expires_at` and folds it into the
  same atomic `UPDATE`.
- `edit_invitation`: when `changes["preferred_visit_date"]` is set **and
  differs from the stored date** (the edit modal resubmits the whole form,
  so presence alone would clobber extensions on every save), add
  `changes["expires_at"] = _end_of_visit_day_utc(changes["preferred_visit_date"], tz)`
  before calling `edit_if_eligible(**changes)`. No repository change is
  needed. When the date is absent or unchanged, `expires_at` isn't touched,
  so a staff extension survives an unrelated edit.
- The `checked_in` edit path already strips everything except
  `_LOCATION_EDIT_FIELDS`, so a checked-in visitor's expiry can't move
  through an edit. That is unchanged.
- *Alternative, compute expiry in a DB trigger:* rejected. The timezone
  lookup spans the company table and the WARNING-logging fallback, and a
  trigger would hide business logic from the service layer
  (fastapi-architecture.md §2).

### D3. QR visit-date gate uses the same resolver

`check_in_by_qr_token` computes `today_local` from `_resolve_visit_timezone`.
Otherwise, between 00:00 and 05:30 IST on the visit day the gate (UTC date)
would say "too early" while the expiry (IST) says "valid". The repository's
atomic `UPDATE` already takes `today_local` as an argument, so no
repository change is needed.

### D4. Backfill: tenant Alembic data migration, targeted by the old-TTL signature

New revision under `alembic_tenant/versions/`, `down_revision =
"e5f7a9b1c3d4"` (current single head). It is data only (no DDL), so it runs
for every tenant through the normal provisioning/upgrade path
(database-architecture.md §5).

Logic, all in SQL in one statement per schema:

```sql
UPDATE {schema}.invitations i
SET expires_at = ((i.preferred_visit_date + time '23:59:59')
                  AT TIME ZONE :zone)
WHERE i.preferred_visit_date IS NOT NULL
  AND i.status IN ('pending','submitted','approved','checked_in')
  AND abs(extract(epoch FROM (i.expires_at - i.created_at)) - 168*3600) < 5
```

(`invitations` has no `deleted_at` column, so there's no soft-delete
filter.)

- **Resolved zone:** computed in Python inside the migration. Read
  `companies.default_timezone` (singleton) and `global.tenants.timezone` for
  this schema, then validate each with `zoneinfo.ZoneInfo` using the same
  precedence as D1. Pass the result as a bound parameter. Don't import
  `vmss_api.invitations.service` from the migration; migrations must not
  depend on application code that will keep changing.
- **Old-TTL signature (`≈ created_at + 168h`, ±5 s):** this is what limits
  the update to rows that were never re-derived. It skips staff extensions
  and rows that already went through the end-of-day rule (approved or
  rescheduled after `9478fc5`). In dev, `expires_at - created_at` is about
  8 ms over 168h. ±5 s allows for slow inserts and still can't match a
  deliberate value.
- Address tables the way `e5f7a9b1c3d4_add_branch_building_form_fields.py`
  does: `schema = op.get_context().version_table_schema`, then
  explicitly qualified `text(f"... {schema}.invitations ...")`. Raw `text()`
  isn't rewritten by `schema_translate_map`, so an unqualified name would
  resolve against the wrong schema or none.
- **Downgrade:** no-op. The previous values were wrong, and there's nothing
  worth restoring.
- *Alternative, one-off script in `scripts/`:* rejected. It would have to be
  run by hand per environment and per tenant, and future tenants
  provisioned from a pre-fix dump would miss it.

### D5. Remove `invitation_token_ttl_hours`

Delete the field from `core/config.py`, its line from `.env.example`, the
`INVITATION_TOKEN_TTL_HOURS` entries in `CI-CD/k8s.yml` and
`CI-CD/Openstack-K8.yml`, and its row in `docs/features/invitations.md`.
Nothing reads it after `9478fc5`. `Settings` uses `extra="ignore"`, so an
environment or local `.env` that still sets it keeps booting. That makes
the pipeline-variable cleanup safe to do in any order. Per
git-workflow.md §5–6, `.env` itself is never staged.

## Risks / Trade-offs

- [Company timezone changed after invitations exist] → Existing rows keep
  their old expiry until the next reschedule/edit/approve. That's accepted,
  because changing a timezone mid-flight is rare and admin-initiated.
- [Backfill shortens a pass that was actually valid later] → Only rows still
  carrying the untouched creation TTL are changed, and that TTL never meant
  anything for the visit. A visitor whose visit day has already passed was
  never meant to have access after it.
- [Backfill makes some rows expire immediately] (visit day already in the
  past) → Correct by intent. They drop off the dashboard's "upcoming" list,
  which is the fix.
- [QR image links in already-sent emails embed `old_expires_at + 7d`] → The
  image URL may outlive the pass, but every check-in validates the live
  `expires_at` (`invitations/models.py` note: "expiry is always read live"),
  so this is cosmetic only.
- [Extra company lookup per request] → It's a single-row indexed read, and it
  reuses the instance already loaded in `create_invitation`.

## Migration Plan

1. Deploy code and run `alembic upgrade head` for global (no-op), then the
   tenant upgrade for every tenant schema (the existing provisioning/upgrade
   path), which applies the backfill revision.
2. Verify in dev:
   `SELECT tracking_id, preferred_visit_date, expires_at AT TIME ZONE 'Asia/Kolkata' FROM tenant_default.invitations WHERE status IN ('submitted','approved');`
   `INV-D127D29A` should show `2026-10-02 23:59:59` and `INV-2015854C` should
   show `2026-10-20 23:59:59`.
3. Rollback: revert the code. The data migration's downgrade is a no-op,
   and the realigned values stay valid under the old code too.

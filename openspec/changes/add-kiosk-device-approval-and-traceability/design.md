## Context

See proposal.md for motivation. The existing `kiosks` table is a flat admin CRUD record (name/description/active/hidden) with no device identity, branch, or check-in link; it is deliberately **not reused or modified**. There is no device registration endpoint; walk-in registration uses the global-schema `RegistrationDeviceKey` (`X-Device-Key`), also left untouched. Public check-in/out endpoints (`invitations/router.py`, `router_v2`) resolve the tenant via `track_default_tenant` and record no device. `Invitation` already has `branch_id`, `building_id`, `check_in_status`, `checked_in_at`, `checked_out_at`. There is no tenant settings store.

## Goals / Non-Goals

**Goals:** a dedicated device model serving both admin pages via filters; approval-gated enablement; device traceability on check-in/out; optional admin-toggled branch/building guard; additive API only.

**Non-Goals:** changing or migrating `kiosks`, `RegistrationDeviceKey`, or walk-in auth; merging `ReceptionDesk`/`SecurityGate` (physical locations) into devices; device secrets (a `device-id` is an identifier, not a credential); hardware integration.

## Decisions

1. **New `devices/` feature package and `devices` table** (`Base, TimestampMixin`): `id`, `device_id` String(255), `name`, `branch_id` FK branches, `building_id` FK buildings nullable, `operating_mode` String(20), `approval_status` String(20), `is_active` bool default false, `approved_at`, `approved_by_user_id`, `deleted_at`. Partial unique index on `device_id WHERE deleted_at IS NULL`. Enums validated at the API boundary (same posture as `gate_type`). Alternative of extending `kiosks` rejected per direction: it was built as a standalone list and has no device semantics.
2. **One list, two pages.** Reception Desks = `operatingMode=kiosk`, Security Gates = `operatingMode=security`. "Disabled" = approved with `is_active=false`; only `pending|approved` is stored.
3. **Approval implies enablement; enable/disable guarded.** Registration creates `pending`/inactive; approve sets approved + active; enable/disable on pending → 409. Separate POST actions so each is permissioned and audited distinctly.
4. **Permissions**: `devices:view`, `devices:manage` (enable/disable/delete), `devices:approve`; settings toggle uses `settings:view`/`settings:manage` if present in `auth/rbac_catalog.py`, else adds them. Propagate to existing tenants' Admin role as prior permission additions did.
5. **Public registration**: `POST /api/v1/devices/register`, unauthenticated, per-IP `@limiter.limit`, tenant via the default-tenant resolver other public endpoints use (never from the body). Upsert by `device_id`; an existing record is never mutated (prevents self-relocation after approval). Branch/building validated active and building∈branch.
6. **`device-id` header on check-in/out**: shared dependency `devices/deps.py::resolve_checkin_device` loads the live device from the tenant session; 403 unless approved and active; `None` when absent (backward compatible). Applied to tracking-ID check-in, QR check-in/out (v2) and staff check-out (v1).
7. **Traceability storage**: `invitations.check_in_device_id` / `check_out_device_id` (nullable FK `devices.id`, indexed). Written only on a real state change (idempotent repeats are no-ops); check-in clears the check-out device on re-entry. Audit entries carry `device_id`. Responses expose `checkInDevice`/`checkOutDevice` via `joinedload`.
8. **Location validation in `invitations/service.py`** check-in paths, after eligibility checks and before the state change so rejection is side-effect free. Branch mismatch → 422; else if invitation has a building and the device's differs (including device with none) → 422. Skipped with no device header or setting off.
9. **Setting storage**: new tenant table `tenant_settings` (single row, `enforce_kiosk_location_validation BOOLEAN NOT NULL DEFAULT true`); absence ≡ true. `GET/PUT /api/v1/admin/settings/kiosk-location-validation`, audited. Redis/`.env` rejected (not durable / not admin-editable per tenant).
10. **List query**: single SELECT with `joinedload` of branch and building for names; filters/sort whitelist per api-conventions §1.
11. **Docs/OpenAPI**: `response_model=Envelope[...]` on all routes; add `devices` to `_TAGS_METADATA` and `api.py`; new `docs/features/devices.md`.

## Risks / Trade-offs

- [Check-ins without `device-id` skip validation] → header optional so existing web/staff clients keep working; enforcement is bypassable by omission. Later, require it on QR/public endpoints once the mobile app ships it.
- [`device-id` is spoofable] → traceability is best-effort, not authentication; a per-device secret (like `RegistrationDeviceKey`) is a recommended follow-up.
- [Two device concepts coexist: `kiosks` and `devices`] → intentional per direction; document in `docs/features/devices.md` that `kiosks` is unrelated to check-in.
- [New permissions missing on existing tenants' Admin role] → 403 until granted; seed/migration step mirrors earlier rollouts.
- [Registration flood of pending rows] → rate limit, unique `device_id`, length validation, admin delete.

## Migration Plan

1. One tenant Alembic revision (merge-head aware): create `devices` and `tenant_settings`, add invitation device FK columns. Purely additive; no backfill.
2. Apply to every tenant schema; seed new permissions and Admin grants.
3. Rollback: downgrade drops the new tables/columns; recorded device history is lost.

## Open Questions

- Should security-device enable/disable need a stricter permission than reception kiosks? Defaults to the same `devices:manage`.
- Whether to add a device secret now (see Risks) — deferred; does not change specs or tasks.

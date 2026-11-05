## Why

Today a badge can only be printed after reception confirms the visitor's ID (`id_not_verified` is part of the print gate). Some tenants want to hand out the badge first and verify the ID later, but still must not let an unverified visitor through the door. Verification therefore needs to move from "required to print" to "required to check in" for those tenants.

## What Changes

- Add a per-tenant boolean `badge_print_requires_id_verification` (default `true`, so current behaviour is unchanged), editable by admins through `PATCH /api/v1/tenants/me/settings` and exposed in `TenantOut`.
- When it is `false`, the print gate (`checkin/service.py::unmet_print_conditions`) no longer reports `id_not_verified`. `photo_missing` and `visit_not_approved` still apply. Print and reprint (reception and kiosk) both honour this.
- When it is `false`, check-in (`invitations/checkin.py::_perform_check_in`, which covers badge-scan check-in, re-entry, desk and tracking-ID check-in) is rejected with `409` and a specific `id_not_verified` detail unless `id_verified_at` is set. Check-out is never blocked.
- The existing verify-id endpoints (reception and kiosk) are unchanged and remain the way to clear that check-in gate.
- The search row and the verify-id response already expose `idVerifiedAt`, so clients can show the pending-verification state; no new fields are needed there.

## Capabilities

### Modified Capabilities
- `badge-print-flow`: the print gate's ID-verified condition becomes tenant-configurable, and check-in enforces ID verification when the print gate does not.

## Impact

- Code: `tenant/models.py`, `tenant/schemas.py`, `tenant/router.py` (+ repository `set_flags` if it whitelists names), `checkin/service.py`, `invitations/checkin.py`, kiosk schemas if they echo tenant flags.
- Database: one global-schema migration adding `tenants.badge_print_requires_id_verification` (`server_default true`) with downgrade. No tenant migration.
- API: additive field on tenant settings; print endpoints accept requests they used to `409`; check-in may now `409` for tenants that opt in. No change for tenants that do not.
- Docs: `docs/features/checkin_badge.md`, `docs/features/tenant.md`.
- Frontend (separate repos): portal/kiosk show an "ID not verified" prompt on check-in `409`, and add the admin toggle.
- Out of scope: auto-verifying, changing photo requirements, or gating check-out.

## Assumptions to confirm

- The skip option is a per-tenant admin setting, not a per-print request flag.
- Check-in enforcement applies only to tenants with the option turned on, so tenants on the default see no new `409`s.
- It only takes effect when the badge print flow is enabled for the tenant.

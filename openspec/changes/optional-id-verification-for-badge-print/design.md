## Context

`unmet_print_conditions(invitation)` hard-codes three conditions. `_perform_check_in` has no ID check at all, because until now a printed badge implied a verified ID. Tenant switches live as booleans on the global `tenants` row, set via `TenantRepository.set_flags` and `PATCH /tenants/me/settings`.

## Decisions

1. **Tenant boolean, default `true`.** `badge_print_requires_id_verification` sits beside `badge_print_flow_enabled`. Default `true` keeps current behaviour and makes the migration safe. Rejected: a per-request `skipIdVerification` flag on the print call, since that lets any reception user bypass the policy and gives no tenant-level control.
2. **`unmet_print_conditions` takes the tenant flag.** Signature becomes `unmet_print_conditions(invitation, *, require_id_verification: bool)`; callers in `_create_print` (reception and kiosk share it) pass the tenant's value. Only `id_not_verified` is conditional.
3. **Enforce at the single check-in choke point.** `_perform_check_in` already serves every check-in path, so the check goes there, after the idempotent already-checked-in return and the archived/watchlist checks, before `check_in_if_eligible`. It raises `409` with detail `ID not verified; verify ID before check-in`. It applies only when `not tenant.badge_print_requires_id_verification` and the badge flow is on, so default tenants are untouched.
4. **Re-entry.** A visit that checked in already has `id_verified_at` set, so re-entry passes. A visit stepped out and never verified cannot exist under this rule.
5. **Race safety.** The pre-check gives the specific reason; also add `Invitation.id_verified_at.is_not(None)` to `check_in_if_eligible`'s atomic `WHERE` only when the rule applies, so a concurrent change cannot slip through. If this proves invasive, keep the pre-check only and note it.

## Risks / Trade-offs

- A tenant that turns the option on with already-printed, unverified badges will see check-in `409`s until verified. Mitigation: documented, and the verify-id endpoint is idempotent and cheap.
- Check-in call sites that pass `tenant` as a different type (`# type: ignore[arg-type]` in `checkin/service.py`) must expose the flag; verify at apply time.

## Migration

Global Alembic migration adds the column `server_default=true`; downgrade drops it. Existing rows become `true`.

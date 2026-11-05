## Why

The backend now lets a tenant print a badge before the visitor's ID is verified, and enforces ID verification at check-in instead. Today the portal assumes ID verification always comes first: reception's print flow tells the user to verify ID before printing, and the badge-scan check-in has no handling for the new "ID not verified" 409. Admins also have no way to choose the behaviour. The change is additive: tenants that do not opt in see no difference.

## What Changes

- Read the new tenant field `badgePrintRequiresIdVerification` (boolean, default `true` when absent) from `GET /tenants/me`; admins with `tenants:update` change it via `PATCH /tenants/me/settings` with `{ "badgePrintRequiresIdVerification": boolean }` (omitted fields are not changed).
- Add an admin toggle "Require ID verification before printing badge" next to "Enable badge printing" in Organisation Configs, hidden/disabled while the badge print flow is off.
- Reception badge printing: stop presenting ID verification as a precondition when the server allows printing without it. The Print action is never blocked client-side on `idVerifiedAt`; the server's 409 (`photo_missing`, `visit_not_approved`, and `id_not_verified` only when the setting is true) decides. The row indicator reads "ID pending" instead of "ID not verified".
- Badge-scan check-in: map the 409 "ID not verified; verify ID before check-in if the visit has no idVerifiedAt" to a dedicated "ID verification required" state instead of a generic error.
- Provide a "Verify ID" prompt for that 409 wherever the portal knows the visit and the user is staff (`POST /checkin/{visitId}/verify-id`, idempotent), then retry the check-in once on explicit user action.
- Check-out and re-enter are untouched (never blocked by this).
- Out of scope: the kiosk app (separate codebase) and portal screens that do not exist yet (desk check-in, tracking-ID check-in). See design.md.

## Capabilities

### New Capabilities
<!-- None -->

### Modified Capabilities
<!-- These capabilities are introduced by the in-flight change `add-badge-print-flow`; this change only adds requirements to them and must be archived after it. -->
- `admin-badge-print-setting`: adds the "require ID verification before printing" toggle and its dependency on the badge print flow toggle.
- `reception-badge-printing`: print no longer assumes ID is verified; "ID pending" indicator; ID-required 409 handling.
- `badge-scan-check-out`: badge-QR check-in handles the "ID not verified" 409 with a Verify ID prompt and retry.

## Impact

- `src/domain/entities/checkin-schema.ts`: tenant read/settings schemas gain `badgePrintRequiresIdVerification`.
- `src/data/repositories/tenant-settings-repository.ts`, `src/infrastructure/tenant-settings-repository.ts`, new use cases, `src/composition-root.ts` (`AppDependencies`).
- `src/presentation/pages/admin-organisation-configs/` (`BadgePrintFlowCard`, its hook).
- `src/presentation/pages/reception-badge-printing/` (row indicator, copy), `src/presentation/utils/badge-print-errors.ts` (new ID-not-verified check-in classifier).
- `src/presentation/pages/badge-scan/` (409 state and Verify ID prompt).
- Depends on the backend release carrying the setting; absent field defaults to `true`, so shipping first is safe.

## Context

The portal's tenant settings client (`TenantSettingsRepository`) already reads `badgePrintFlowEnabled` / `zoneAccessEnabled` from `GET /tenants/me` and PATCHes `/tenants/me/settings`. Reception uses `BadgeResultRow`, which already hides nothing based on `idVerifiedAt` for Print but labels the state "ID not verified", and maps `id_not_verified` in `badge-print-errors.ts`. The public badge-scan page (`useBadgeScan`) calls `POST /checkin/badge/check-in` with no staff token and only the QR token, so it never learns a `visitId`. Reception users hold `visitors:print_badge` but not `tenants:read`, so they get 403 on `GET /tenants/me`. See proposal.md for motivation.

The repo contains no desk check-in or tracking-ID check-in screens, and the kiosk is a separate app; only the badge-scan check-in exists here.

## Goals / Non-Goals

**Goals:**
- Admins can flip the new setting; absent field behaves as `true` (today's behaviour).
- Reception never client-blocks printing on ID; server 409 is the source of truth.
- Badge-scan check-in turns the new 409 into a clear message, with a Verify ID path where the visit is known.

**Non-Goals:**
- Kiosk changes, and building new desk/tracking-ID check-in screens.
- Making reception read the tenant setting (they lack `tenants:read`).
- Any change to check-out, re-enter, or already checked-in visits.

## Decisions

- **Tenant setting plumbing.** Extend `TenantMeResponseSchema` / `TenantSettingsResponseSchema` with `badgePrintRequiresIdVerification: z.boolean().optional().default(true)`; add `getBadgePrintRequiresIdVerification` / `setBadgePrintRequiresIdVerification` to the port and adapter, plus two use cases wired in the composition root. The PATCH body contains only the one field (server leaves omitted fields unchanged). Alternative: one generic `updateSettings(partial)` method; rejected to match the existing per-setting pattern.
- **Admin toggle.** Add a second `ToggleSwitch` in `BadgePrintFlowCard`, driven by an extended `useBadgePrintFlowSetting` (optimistic update, revert and toast on failure, as the existing toggle). It is `disabled` with helper text when the print flow is off; its value is preserved, not reset.
- **Reception does not read the setting.** Because reception gets 403 on the tenant read, the print step does not branch on the setting. Print stays enabled; `describePrintError` keeps the `id_not_verified` copy for tenants that require it. This avoids an extra probe and cannot disagree with the server. The "ID not verified" label becomes "ID pending" and its styling stays neutral (not an error), since pending is a valid state when the setting is off. Alternative: hide the verify step when the setting is false (as the backend note suggests); rejected for reception because the setting is unreadable there, and the verify action is harmless and idempotent.
- **Classifying the check-in 409.** Add `isIdNotVerifiedError(error)` in `badge-print-errors.ts`: `ApiError` with status 409 and message matching `/id not verified/i`. This is checked before the generic message fallback in `describeScanError`; the scan hook's outcome gains `{ kind: 'id-required' }`.
- **Verify ID prompt on the scan page.** The scan call has no `visitId`, and `verify-id` needs a staff token, so the public page cannot verify. It shows the "ID verification required — please see reception" state. A "Verify ID" action is only rendered when a visit id is available to the caller (a future staff-side check-in screen reusing `isIdNotVerifiedError` + `VerifyCheckinIdUseCase`); the retry is an explicit button, never automatic, and runs once. Reception can already verify via the Badge printing screen, so the visitor is not stuck.
- **No new endpoints.** `CHECKIN_VERIFY_ID` and `CHECKIN_BADGE_CHECK_IN` already exist.

## Risks / Trade-offs

- [Reception sees "ID pending" for tenants that require ID] → the Print 409 still explains it; copy is neutral and the action is one click.
- [Message regex drifts if backend rewords] → matching is on the substring "ID not verified" with fallback to the server's own message, so worst case is the generic display.
- [Public scan page cannot self-serve verification] → intentional (verification is a staff attestation); directs to reception.
- [Backend not yet deployed] → absent field defaults to `true`; PATCH of an unknown field could be rejected on an older backend, surfaced via the normal failure toast.

## Open Questions

- Should a staff-side check-in screen (desk / tracking ID) be added to the portal later? Not needed for this change.

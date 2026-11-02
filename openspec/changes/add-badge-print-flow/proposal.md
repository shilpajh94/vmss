## Why

Reception today can issue a PNG badge (`POST /invitations/{id}/badge`) whose QR is the invitation's check-in token, issued at approval. The new badge flow changes the model: the visitor arrives, reception finds the visit, confirms their ID, captures a photo, and prints a PDF badge whose QR is generated at reception, bound to that visit day, and revocable on reprint. That badge then drives checkout and same-day re-entry by scan. The flow must ship dark: behind a flag, as new code only, with the existing invitation check-in, badge and notification behavior unchanged when the flag is off.

## What Changes

- Add `BADGE_PRINT_FLOW_ENABLED` (default `false`) to settings, `.env.example` and `docs/features/configuration.md`, plus a per-tenant `badge_print_flow_enabled` boolean on the tenant profile, editable by admins. The flow is on only when both are true. A flag dependency returns `404` on every new endpoint when it is off.
- Add a new `checkin/` feature package (router, service, schemas, models, repository, badge renderer, tasks) registered in `api.py`, `_TAGS_METADATA` and the docs test.
- Add permission `visitors:print_badge`, granted to Reception and Admin.
- Add reception visit search by name, phone, invitation code (`trackingId`) or numeric check-in code (the "OTP" the visitor receives by SMS).
- Add an ID-verification confirmation (`POST /checkin/{visit_id}/verify-id`), recorded on the visit, so "ID verified" is an explicit reception act rather than inferred.
- Add a print gate: visit is `approved`/`checked_in`, photo captured, ID verified.
- Add append-only `badge_prints` (visit, printed_by, time, `jti`, active, reprint reason) and a badge QR token that is signed, valid for that visit day only, and carries the `jti`.
- Add a PDF badge renderer (name, host, photo, date, QR) offloaded with `anyio.to_thread`. The existing PNG badge code is untouched.
- Add `POST /checkin/{visit_id}/badge` (print, returns PDF, `Idempotency-Key`) and `GET /checkin/{visit_id}/badge` (reprint with a required reason; deactivates the previous `jti`). Every print and reprint is audited by a background task.
- Add checkout by badge QR scan (fallback: reception search then checkout), and same-day re-entry by badge QR scan, both rate-limited and audited.
- Add a "bring your ID" callout to the visitor approval **email** only (not SMS/WhatsApp), only when the flow is on for the tenant. Approved by the user.

## Capabilities

### New Capabilities
- `badge-print-flow`: flag gating, reception search, ID verification, print gate, badge QR token, PDF badge print/reprint, badge-scan checkout and re-entry, and their audit and permission rules.

### Modified Capabilities
- `environment-configuration`: new `BADGE_PRINT_FLOW_ENABLED` setting.
- `notifications`: approval text variant when the flow is on.
- `auth`: new `visitors:print_badge` permission and its default role grants.

## Impact

- Code: new `src/vmss_api/checkin/`; small edits to `core/config.py`, `core/deps.py` (flag dependency), `tenant/models.py|schemas|router|service`, `auth/rbac_catalog.py`, `invitations/notifications.py` (flag branch only), `api.py`, `main.py`, `.env.example`.
- Database: one global-schema migration (`tenants.badge_print_flow_enabled`); tenant migrations for `badge_prints` and the `id_verified_*` columns on `invitations`; a data migration granting the new permission to existing Reception and Admin roles (see how earlier `grant_*` migrations did it).
- API: new endpoints under `/api/v1/checkin` and `PATCH /api/v1/tenants/me/settings`; additive only, no breaking change.
- Config: new env var, no new dependency expected beyond a PDF library (see design.md Decision 6).
- Docs: `docs/features/checkin_badge.md`, `configuration.md`, `tenant.md`.
- Frontend (separate repos): portal and mobile add reception search, verify-ID, print and scan screens behind the same flag.
- Out of scope: any change to the existing PNG badge, existing check-in/out endpoints, or the invitation QR token.

## Open items to confirm before apply

- The reprint endpoint is specified as `GET`, which mutates state. See design.md Risks.

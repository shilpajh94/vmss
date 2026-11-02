## Why

The backend now supports a badge print flow for reception: find a visit, confirm the physical ID was checked, print a PDF badge with a signed QR, reprint with a reason, and scan the badge (no login) to check out or re-enter. The whole `/api/v1/checkin/*` surface is dark-launched: it returns 404 unless both the server flag `BADGE_PRINT_FLOW_ENABLED` and a per-tenant toggle are on. The UI has no way to use any of this, or to let an admin switch it on.

## What Changes

- Add a tenant-settings client: read `badgePrintFlowEnabled` from `GET /tenants/me`; admins with `tenants:update` toggle it via `PATCH /tenants/me/settings` `{ "badgePrintFlowEnabled": boolean }`.
- Add a Reception "Badge printing" screen, shown only when the tenant flag is on AND the user has `visitors:print_badge`:
  - Search (`GET /checkin/search`, paged) by name, phone, invitation code or numeric SMS check-in code; rows show status, check-in status, photo, ID-verified and active-badge indicators.
  - "ID verified" action (`POST /checkin/{id}/verify-id`, idempotent).
  - Print badge (`POST /checkin/{id}/badge`, PDF response, `Idempotency-Key` reused on retry) and open the PDF for printing.
  - Reprint (`GET /checkin/{id}/badge?reason=`) only behind a confirm dialog with a required 1-255 char reason; never prefetched or auto-called.
  - Print-rule 409s (`visit_not_approved`, `photo_missing`, `id_not_verified`, badge already active, reprint before first print) surface as specific, actionable messages.
- Add a login-free badge scan page with Check-out and Re-enter actions (`POST /checkin/badge/check-out`, `/re-enter`, body `{ token }`), with distinct handling for 400 "Invalid badge token" and 429.
- Treat any 404 from `/checkin/*` as "feature off": hide the flow and show a neutral unavailable state, not an error.
- Extend `ApiClient` to return binary (PDF) success bodies, since it currently always parses JSON through Zod.
- No change for email/SMS/WhatsApp: the "Please bring your ID" email callout is backend-only.

## Capabilities

### New Capabilities
- `reception-badge-printing`: feature gating, search, ID verification, print, and confirmed reprint for reception.
- `badge-scan-check-out`: unauthenticated QR-token check-out and same-day re-entry.
- `admin-badge-print-setting`: admin toggle for the tenant flag.

### Modified Capabilities
<!-- None: Reception navigation entry is specified inside reception-badge-printing -->

## Impact

- `src/data/api/api-endpoints.ts`: new entries for tenant read/settings and the six checkin routes (scan routes `hasToken: false`).
- `src/data/api/api-client.ts`: binary-response path (e.g. `makeBlobRequest`) plus `Idempotency-Key` and optional extra headers; blob path must still honor `hasToken` and `X-Branch-ID` behaviour used elsewhere.
- `src/domain/entities/`: tenant and checkin Zod schemas.
- New ports, use cases, infrastructure adapters, composition-root wiring and `AppDependencies` entries.
- Presentation: new reception page, public scan route, admin settings control; permission check for `visitors:print_badge`.
- Depends on the backend deploying with the flag; the tenant flag defaults off so shipping is safe.

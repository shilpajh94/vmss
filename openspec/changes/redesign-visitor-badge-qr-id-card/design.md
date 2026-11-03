## Context

`add-badge-print-flow` has the backend render the badge PDF (`POST /checkin/{id}/badge`, `GET /checkin/{id}/badge?reason=`); the frontend opens the blob in a new tab and explicitly lists client-side QR rendering as a non-goal. The signed QR token, purpose and host never reach the frontend, and `CheckinSearchRow` has no photo URL, purpose or host. See proposal.md - Why. The user chose to render the badge in the frontend.

## Goals / Non-Goals

**Goals:**
- Render the ID-card badge in React/Tailwind and print it from the browser.
- Encode the existing signed token as a QR.

**Non-Goals:**
- Designing the scan page or changing token semantics.
- Per-tenant badge templates or a designer UI.
- Keeping the PDF path once the JSON path ships (see Migration).

(Implemented: the adapter accepts JSON or PDF by response type, so the old PDF keeps working until the backend ships JSON. See backend-request.md.)

## Decisions

- **Backend returns badge JSON.** Print/reprint respond with `{ token, visitorName, purpose, hostName, photoUrl }` (exact shape agreed with backend). Alternative: keep the PDF and embed a design request, rejected since the user chose frontend rendering. The new Zod schema lives in `checkin-schema.ts`; the adapter uses `makeRequest` instead of the blob path.
- **QR via a small client library** (e.g. `qrcode.react` SVG output), picked at implementation. SVG scales cleanly when printed and needs no network call, so the token never leaves the browser.
- **Print with a print-only stylesheet and `window.print()`**, showing a hidden-on-screen `BadgeCard` mounted in the reception page, sized to a CR80 ID card (85.6x54 mm, landscape per reference). Alternative: a popup window, rejected since popup blockers already caused the `pdfLink` fallback.
- **Layout follows the reference**: teal header band with "VISITOR ID CARD", photo right, label/value rows left, QR bottom-left in place of the barcode. Colours come from `--color-*` theme tokens, not hard-coded hex.
- **Token held in hook state only** until `afterprint`, then cleared, to satisfy the token-handling requirement.
- Layering stays as in the rules: presentation consumes use cases via `useAppDependencies()`; the QR library is used only in presentation.

## Risks / Trade-offs

- [Backend does not yet expose the token/fields] → Blocking dependency; agree the contract first, gate behind the existing flag.
- [Photo URL may be auth-protected, so `<img>` fails] → Fetch through `ApiClient` as a blob and use an object URL, revoked after print.
- [Printed QR too dense to scan] → Use error-correction level M and a minimum 20 mm size; test with the real scan page.
- [Browser print margins/scale differ] → `@page` size plus a manual print check in Chrome and Firefox.
- [Reprint kills previous QR] → Existing confirm dialog stays; render only after a successful response.

## Migration Plan

Ship behind the existing tenant flag once the backend JSON response is live. Keep the blob path until verified, then remove `openPdf`. Rollback: revert to the PDF path.

## Open Questions

- Exact JSON field names and whether the photo comes as URL or bytes (affects only the adapter and schema, not the specs).

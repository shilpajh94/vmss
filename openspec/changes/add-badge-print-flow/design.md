## Context

All HTTP goes through `ApiClient.makeRequest`, which JSON-parses every response with a Zod schema. The badge POST returns `application/pdf`, so that path needs a binary variant. The scan routes need no token; the QR token is the credential. The frontend has no tenant-settings client yet. See proposal.md.

## Goals / Non-Goals

**Goals:**
- Dark-launch safe: with the flag off nothing is visible and a 404 is never shown as an error.
- Follow the layering rules (endpoint registry -> port -> adapter -> use case -> composition root -> hook).
- Make state-changing GET (reprint) impossible to trigger accidentally.

**Non-Goals:**
- Photo capture UI (the flow only requires `hasPhoto`; capture exists elsewhere or is a separate change).
- Generating or rendering QR codes client-side; the PDF is the badge.
- Email/SMS content, Swagger, or server flag management.

## Decisions

- **Gate = tenant flag AND permission.** A hook reads `badgePrintFlowEnabled` from `GET /tenants/me` and the user's permissions for `visitors:print_badge`. Either missing hides the nav entry and redirects the route. The tenant read may already be fetched for other screens; reuse it if present. Server flag state is invisible to the UI, so any `/checkin/*` 404 also flips the screen to the "unavailable" state.
- **Binary requests.** Add `ApiClient.makeBlobRequest({ endpointConfig, queryParams?, headers? })` returning `Blob`, reusing URL, auth and error handling; error bodies are still JSON envelopes and must be parsed into the same error type as `makeRequest`. Alternative (raw `fetch` in the adapter) is rejected by the data-layer rule.
- **Idempotency key.** Generate `crypto.randomUUID()` per print *attempt* held in component state for the visit, and reuse it for retries until the print succeeds or the visit selection changes; then discard. A new key on a deliberate second print would hit the 409 active-badge rule, which is correct.
- **Printing the PDF.** Create an object URL from the Blob and open it in a new window/hidden iframe and call print; revoke the URL afterward. Popup-blocked fallback: show a "Open badge PDF" link.
- **Reprint safety.** Reprint is a button -> confirm dialog with required reason (1-255, trimmed, counter) -> explicit call. No `useEffect`, prefetch, link `href` or retry wrapper may call it. The dialog warns the previous badge stops working immediately.
- **409 mapping.** Map by the message codes `visit_not_approved`, `photo_missing`, `id_not_verified` to specific copy; other 409s (already active / reprint before print) steer the user to Reprint / Print respectively. Unknown 409 text falls back to the server message.
- **Scan page.** Public route (no auth redirect) takes the QR text via a text field (scanner acting as keyboard) and optionally a `?token=` query param, never auto-submitting. Two explicit buttons. Success shows `trackingId` and new `checkInStatus`. 400 -> "This badge is not valid (wrong day, replaced, or already used)"; 429 -> "Scanning too fast, wait a moment". Token is not logged or stored.
- **Branch scoping.** Reuse whatever existing mechanism sends `X-Branch-ID` for reception calls.
- **Assumption:** the toggle UI lives in existing admin settings (placed on an organisation/settings page) and shows only to users with `tenants:update`; exact page chosen at implementation.

## Risks / Trade-offs

- Backend flag off but tenant flag on -> every call 404s: handled by the unavailable state.
- Popup blockers can stop auto-print -> fallback link.
- Scan page is unauthenticated and rate-limited at 30/min/IP; shared kiosk networks may hit 429 -> clear message, no auto-retry.
- Idempotency key reuse after a failed-then-fixed precondition (e.g. ID verified after a 409) could replay the cached failure on some backends -> regenerate the key after any 409/4xx, reuse only for network/5xx retries.

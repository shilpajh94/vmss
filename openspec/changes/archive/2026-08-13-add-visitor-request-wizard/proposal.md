## Why

The landing page's "Request Visit" button already links to `/visitor/request`, but that route renders nothing — the destination was explicitly deferred when the landing page shipped. The Figma file "VMS" (node `5:51` and its sibling frames) defines the actual request flow: a 6-step wizard (Visitor Info, Visit Info, Carried Items, Vehicle Info, Consent Agreement, Review & Confirm) that captures everything needed to issue a visitor pass. This change builds that flow and gives the landing page's CTA a real destination.

## What Changes

- Register `/visitor/request` and add the **Visitor Request Wizard**: a 6-step form matching the Figma design's fields, copy, and layout, sharing the landing page's header/footer chrome pattern.
  1. **Visitor Info** — Individual/Group toggle; individual visitor fields (including address, visitor category, and an optional profile image), or a primary contact plus a dynamic list of additional visitors (group), each carrying the same fields.
  2. **Visit Info** — purpose, host, preferred date/time, duration, location, building, department, notes.
  3. **Carried Items** — checklist of item categories visitors declare for security clearance, plus optional description.
  4. **Vehicle Info** — dynamic list of vehicles (type, plate, make/model, color).
  5. **Consent Agreement** — terms & conditions text plus three required consent checkboxes.
  6. **Review & Confirm** — **not present in the Figma file** (the design stops at step 5). This change adds a standard summary-of-all-steps + submit screen, since a wizard needs a final confirmation step to exist at all. On successful submission it shows the returned tracking ID; on failure it shows an error and lets the visitor retry.
- Define the first real backend contract in this app: a `POST` endpoint to create a visit request (JSON) and a dedicated upload endpoint (multipart) reused for both ID-proof documents and visitor profile images, per the earlier decision to define real API contracts and a real upload endpoint rather than stub them.
- Extend `ApiClient` with multipart/file-upload support — the current `makeRequest` only sends JSON bodies. `data/api/api-endpoints.ts`, the Zod schemas, the repository port/adapter, and use cases are all new (this is the first feature to populate those previously-empty directories).
- Add shared form primitives (`src/presentation/components/ui/`) — text field, select, checkbox, file upload, segmented toggle — since all 6 steps need them within this same change (unlike the landing page's header/footer, this is immediate in-change reuse, not speculative).

## Capabilities

### New Capabilities
- `visitor-request-wizard`: the multi-step visit-request flow — form behavior, validation, submission, and the response the visitor sees.

### Modified Capabilities
(none — `app-shell` and `visitor-portal-landing` are unaffected; the landing page's CTA already specifies "navigates to the visit-request route," which this change satisfies by giving that route a real page)

## Impact

- `src/domain/entities/`: new Zod schemas for visitor, vehicle, and visit-request payloads/responses.
- `src/data/api/api-endpoints.ts`: two new entries (create visit request, upload ID document).
- `src/data/api/api-client.ts`: new multipart upload capability alongside the existing JSON `makeRequest`.
- `src/data/repositories/`, `src/data/use-cases/`, `src/infrastructure/`: new port, adapter, and use cases for submitting a request and uploading a document.
- `composition-root.ts` / `AppDependencies`: exposes the new use cases to the UI for the first time.
- `src/presentation/components/ui/`: new shared form primitives.
- `src/presentation/pages/visitor-request/`: new page, step components, and form-state hook.
- `src/App.tsx`: registers the `/visitor/request` route.
- `src/presentation/pages/visitor-portal-landing/Components/PortalHeader.tsx` → promoted to a shared `src/presentation/components/PortalHeader.tsx` (with an optional back-chevron prop), since this wizard is now the second consumer of that header — pure refactor, no behavior change to the landing page.
- No changes to the `/visitor/track` route or the tracking feature — still a separate, later change.

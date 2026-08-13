## Why

The landing page's "Track Your Visit" button links to `/visitor/track`, but that route renders nothing — the destination was explicitly deferred when the landing page shipped. The Figma file "VMS" (node `5:163`, "visitor-portal-track-request") defines the actual tracking screen: a visitor enters their tracking ID and sees the current status of their visit request. This change builds that screen and gives the landing page's second CTA a real destination, completing the three-page visitor portal scope (landing → request wizard → track request).

## What Changes

- Register `/visitor/track` and add the **Track Request** page: a tracking-ID lookup form and, once a request is found, a status panel showing the tracking ID, status badge, requested date, assigned host, total visitor count, and a 4-stage timeline (Submitted → Under Review → Approved → Visit Day).
- Define a new read-only backend contract: a `GET` endpoint that looks up a visit request by tracking ID and returns its current status, following the same "define the real contract now" approach as the request wizard (`add-visitor-request-wizard`) — the lookup will fail with a network error until a matching backend exists, and that failure is handled explicitly (error shown, retry available).
- The "Forgot Tracking ID? Track via Email" link visible in the Figma design is rendered to match the design but is **not functional** in this change — per scope decision, email-based lookup is deferred to a later change.
- Figma's frame for this screen shows what looks like a duplicated footer-style bar above the actual page header — treated as a Figma authoring artifact and not reproduced; the page uses the same header/footer pattern as the other two portal pages.

## Capabilities

### New Capabilities
- `visitor-track-request`: the tracking-ID lookup and visit-request status display.

### Modified Capabilities
(none — `visitor-portal-landing` already specifies that its "Track Request" action navigates to the visit-tracking route; this change satisfies that by giving the route a real page. No existing requirement text changes.)

## Impact

- `src/domain/entities/`: new Zod schema for the tracking lookup response.
- `src/data/api/api-endpoints.ts`: one new entry (track visit request by tracking ID, `GET` with a query parameter — this repo's `ApiClient` has no path-parameter templating, so the tracking ID is passed as a query string).
- `src/data/repositories/`, `src/data/use-cases/`, `src/infrastructure/`: new port, adapter, and use case for the lookup.
- `composition-root.ts` / `AppDependencies`: exposes the new use case.
- `src/presentation/pages/visitor-track/`: new page and components.
- `src/App.tsx`: registers the `/visitor/track` route.
- Reuses the shared `PortalHeader`/`PortalFooter` (promoted in `add-visitor-request-wizard`) and the existing `SearchIcon` asset from `src/assets/icons.ts`.

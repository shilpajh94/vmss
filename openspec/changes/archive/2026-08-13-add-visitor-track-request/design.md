## Context

`src/App.tsx` registers `/` and `/visitor/request`; `/visitor/track` is linked from the landing page's second CTA but unregistered. `src/data/api/api-endpoints.ts`, `ApiClient`, the domain schemas, and the repository/use-case layers now have an established pattern from `add-visitor-request-wizard` (archived): `API_ENDPOINTS` entries + Zod schemas + a port/adapter/use-case per feature, wired through `composition-root.ts`. `PortalHeader` and `PortalFooter` are already shared components (promoted in that same change) with `PortalHeader` accepting an optional `backTo` prop. `src/assets/icons.ts` already exports `SearchIcon` (used by the landing page's "Track Your Visit" card) — this page reuses it rather than sourcing a new icon.

Source: Figma file `jXdJ0LuzcPY9YxgrnqXle6`, frame `5:163` ("visitor-portal-track-request"). See `proposal.md` for the "Track via Email" scope decision and the note on the frame's duplicated footer-style bar, which this design treats as a Figma authoring artifact and does not reproduce.

## Goals / Non-Goals

**Goals:**
- Tracking-ID lookup and status display match the Figma layout (two-panel: lookup form, status panel) using the existing token set and Tailwind utilities.
- The read endpoint follows the same "define the real contract now" approach as the request wizard, even though no backend exists yet.

**Non-Goals:**
- Email-based lookup — link is present, not wired (see proposal.md).
- Any write/mutation from this page — this is a pure read/lookup feature.
- Polling or auto-refreshing the status while the page is open — each lookup is a single on-demand request.

## Decisions

### API contract: query parameter, not a path parameter
`ApiClient.makeRequest` has no path-parameter templating — every existing endpoint is a static string. Rather than adding that capability for a single new endpoint, this change adds `TRACK_VISIT_REQUEST` as `GET /visit-requests/track` and passes the tracking ID via `queryParams: { trackingId }`, which `makeRequest` already supports via `buildQueryString`.

**Alternative considered**: extend `ApiClient`/`API_ENDPOINTS` to support `{endpoint}/:trackingId`-style templating. Rejected — no other endpoint needs this yet, and adding general path-templating for a single call site is speculative; a query parameter achieves the same lookup with zero client changes.

### Response schema carries explicit render hints, not just raw data
`TrackingLookupResponseSchema`: `trackingId`, `statusLabel` (display text, e.g. "Pending Approval"), `statusTone` (`'success' | 'warning' | 'danger' | 'info'`, mapping directly to the existing color tokens for the status badge), `requestedDate`, `assignedHost`, `totalVisitors`, `timelineStage` (`'submitted' | 'under-review' | 'approved' | 'visit-day'`).

**Alternative considered**: return only `statusLabel` and have the frontend infer badge color and timeline position from that string. Rejected — string-matching business status text for presentation logic is brittle (label wording can change independently of what color/stage it implies); an explicit `statusTone`/`timelineStage` is a contract both sides can rely on.

### Timeline rendering: derive stage state from a single enum
The four timeline stages are rendered by comparing each stage's index to `timelineStage`'s index: stages before are "complete" (success color), the matching stage is "current" (warning color, matching Figma's orange), stages after are "upcoming" (neutral/gray). This mirrors the wizard's `StepSidebar` pattern (index comparison against a current step) rather than inventing a new representation.

### Failure handling: one error state for "not found" and "lookup failed"
Both cases (no matching tracking ID, and a lookup that can't complete — e.g. no backend yet) render the same error state with a retry-friendly message, matching the spec's "Lookup failure is reported without crashing" requirement. `ApiClient.makeRequest` doesn't distinguish HTTP status today (a pre-existing characteristic from the wizard change, not changed here), so any thrown error — 404, network failure, or a response that fails schema validation — is treated the same way.

### Page structure
- `src/presentation/pages/visitor-track/visitor-track.tsx` — page composing the shared `PortalHeader` (with `backTo="/"`), a hero title bar over the same lobby photo used on the landing page, the lookup card, and (once a lookup resolves) the status card, plus the shared `PortalFooter`.
- `src/presentation/pages/visitor-track/hooks/use-visitor-track-lookup.ts` — holds the tracking-ID input, lookup status (`idle | loading | success | error`), and the resolved response; calls the new use case via `useAppDependencies()`.
- `src/presentation/pages/visitor-track/Components/TrackingLookupCard.tsx` and `StatusPanel.tsx` — the two visual panels.

## Risks / Trade-offs

- **Backend doesn't exist yet** → every lookup fails with a network error until a backend implementing `GET /visit-requests/track` exists. Mitigation: expected and handled per the "Lookup failure" requirement, consistent with how the request wizard's submission handles the same situation.
- **"Track via Email" visible but inert** → a visitor may click it expecting it to work. Mitigation: explicit scope decision (proposal.md); revisit when that flow is actually built.

## Migration Plan

1. Domain schema → API endpoint → repository port/adapter → use case → composition-root wiring.
2. Page components (`TrackingLookupCard`, `StatusPanel`) and the lookup hook.
3. Register `/visitor/track` in `src/App.tsx`.
4. No data migration, no feature flag — additive functionality behind a previously-dead route.

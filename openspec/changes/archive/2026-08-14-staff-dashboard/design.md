## Context

The dashboard is the first data-backed staff screen in this codebase. Existing staff-side work (`staff-login`) only has an SSO-initiate call (`hasToken: false`) — no endpoint yet reads or writes anything with a bearer token, and no code currently issues/stores a token (that happens in an SSO callback that is out of scope here, per proposal.md). All existing visit-request plumbing (`VisitRequestSchema`, `HttpVisitRequestRepository`, `submit-visit-request`/`track-visit-request` use cases) models the visitor-facing submission payload and tracking lookup — not the lightweight summary a staff kanban card needs. See proposal.md - Why / Impact for motivation and scope boundaries.

## Goals / Non-Goals

**Goals:**
- Wire the dashboard end-to-end per `.claude/rules/data-api-layer.md` and `clean-architecture.md`: endpoints → schemas → port → adapter → use case → composition root → hook → components.
- Keep the new visit-summary read path separate from the existing visitor-submission write path, since they model different shapes and different auth requirements.
- Implement the route guard and sign-out as presentation-only logic (no new backend calls), consistent with `hasToken` already being a client-side concern.

**Non-Goals:**
- Building the SSO callback / token-issuance flow (assumed to exist by the time this screen renders).
- Server-side search or filtering (search is client-side over the already-loaded list; "Filters" is inert).
- "My actions", "Audit trail", and "Help & Support" behavior beyond being visible and inert.
- Real-time/websocket updates — refresh is manual only.

## Decisions

- **New port instead of extending `VisitRequestRepository`**: add `VisitRequestSummaryRepository` (or similarly named) with a single `list(): Promise<VisitRequestSummary[]>` method, backed by a new `LIST_VISIT_REQUESTS` endpoint (`GET`, `hasToken: true`). Alternative considered: add a `list` method to the existing `VisitRequestRepository`. Rejected — that port's `submit`/`uploadDocument` methods are visitor-facing and token-free; mixing an authenticated staff read into it would blur the port's contract. A new domain schema `VisitRequestSummarySchema` (id, reqId, visitorName, visitorInitials, hostName, scheduledAt, status) captures the card/column shape independently of the full submission schema.
- **New `StaffUserRepository` port** (or extend `StaffAuthRepository`) with `getCurrentUser(): Promise<StaffUser>`, backed by `GET_CURRENT_STAFF_USER` (`GET`, `hasToken: true`) and a `StaffUserSchema` (name, role). Kept on the existing `StaffAuthRepository` since it's the same auth boundary (staff identity), unlike the visit-summary case above.
- **Status column mapping**: `VisitRequestSummary.status` is one of `requested | approved | checked_in | denied` (wire values); the hook groups by this field into the four fixed columns. New statuses the backend might add later are out of scope — the UI only renders the four known columns.
- **Route guard placement**: implemented inside `use-staff-dashboard.ts` (checks `sessionStorage.getItem('token')` on mount and calls `navigate('/staff/login', { replace: true })` if missing), not a separate router-level guard component — there is only one protected route today, so a dedicated guard abstraction would be premature.
- **Sign-out**: presentation-only — `sessionStorage.removeItem('token')` followed by `navigate('/staff/login')`. No backend call, since there is no session-invalidation endpoint in scope.
- **Search**: client-side `Array.prototype.filter` over the loaded list on each keystroke, matching visitor name / host name / REQ ID case-insensitively. No debouncing needed at expected list sizes for this iteration.

## Risks / Trade-offs

- [Two staff-facing ports (`VisitRequestSummaryRepository` new, `StaffAuthRepository` extended) instead of one unified "staff" port] → Mitigation: matches the existing pattern of one port per bounded concern (e.g., `VisitTrackingRepository` vs `VisitRequestRepository` are already separate); keeps each port's method list small and coherent.
- [Assuming a token is already present in `sessionStorage`, with no callback flow yet implemented] → Mitigation: the redirect-to-login guard degrades gracefully (staff simply can't reach the dashboard until the callback flow ships); documented as an explicit assumption in proposal.md.
- [No pagination on `LIST_VISIT_REQUESTS`] → Mitigation: acceptable for current expected volume; revisit if the backend contract needs it later.

## Migration Plan

Additive on the frontend (new files, new endpoint entries) plus one presentation rewrite (`staff-dashboard.tsx`) and one wording-only spec update (`staff-login`). No data migration. Requires the backend to expose `LIST_VISIT_REQUESTS` and `GET_CURRENT_STAFF_USER`; until then the dashboard's error-state requirement (list load failure shows an error message) covers the missing-endpoint case gracefully. Rollback is a straight revert of the changed/added files.

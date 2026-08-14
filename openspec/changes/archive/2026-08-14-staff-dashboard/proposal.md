## Why

Staff currently land on a placeholder page after SSO sign-in. The approved Figma design ("visitor-dashboard", VMS file, node 31:4) defines the real staff landing experience: a kanban-style view of visit requests grouped by status. Staff need this to review, track, and act on visit requests without leaving the dashboard.

## What Changes

- Replace the placeholder `/staff/dashboard` page with the full dashboard layout from Figma: dark sidebar (brand mark, "All visitors" / "My actions" / "Audit trail" nav, "Help & Support" link) and a main workspace.
- Add a workspace header showing the "Visits" title/subtitle, the signed-in staff member's name and role, a manual refresh action, and a sign-out action.
- Add a search bar (filters visitor name, host, and REQ ID client-side) and a "Filters" affordance that is visible but not yet functional (no filter panel behavior defined in the design yet).
- Add a kanban board with four status columns — Requested, Approved, Checked-in, Denied — each with a live count badge, rendering visit request cards (avatar initials, REQ ID, visitor name, host name, scheduled date/time) and an empty state for columns with no requests.
- Add a lightweight route guard on `/staff/dashboard`: if no auth token is present in session storage, redirect to `/staff/login`.
- **BREAKING**: `/staff/dashboard` no longer renders the placeholder described in the `staff-login` spec; it renders the real dashboard.

## Capabilities

### New Capabilities
- `staff-dashboard`: The staff dashboard screen — sidebar navigation, workspace header (current user, refresh, sign out), search, and the visit-requests kanban board, backed by new "list visit requests" and "current staff user" API integrations.

### Modified Capabilities
- `staff-login`: The requirement "Successful SSO sign-in lands on the staff dashboard placeholder" changes — the dashboard is no longer a placeholder; it is the full `staff-dashboard` capability described above.

## Impact

- **New API surface**: `LIST_VISIT_REQUESTS` (GET, token-bearing) and `GET_CURRENT_STAFF_USER` (GET, token-bearing) entries in `src/data/api/api-endpoints.ts`.
- **New domain schemas**: a visit-request summary schema (id/REQ code, visitor name, host name, scheduled date/time, status) and a staff-user profile schema (name, role) under `src/domain/entities/`.
- **New port + adapter**: a dashboard-facing repository (or an extension of the existing visit-request port) for listing visit request summaries, and an extension of `StaffAuthRepository` (or a new port) for fetching the current staff user; adapters under `src/infrastructure/`.
- **New use cases**: `ListVisitRequestsUseCase`, `GetCurrentStaffUserUseCase` under `src/data/use-cases/`, wired through `composition-root.ts` and exposed via `AppDependencies`.
- **Presentation**: rewrite `src/presentation/pages/staff-dashboard/staff-dashboard.tsx`, add feature components under its `Components/` folder, and a `use-staff-dashboard.ts` hook under its `hooks/` folder that loads data via `useAppDependencies()`, handles refresh/search/sign-out, and performs the auth-token route guard.
- **Assumption**: this change assumes a staff auth token is already present in `sessionStorage` by the time `/staff/dashboard` renders (issued by the existing SSO flow's eventual callback handling). Building the SSO callback/token-issuance mechanism itself is out of scope here; the dashboard only checks for the token's presence and redirects to `/staff/login` if it is missing.
- **Assumption**: "Filters" is rendered per the design but performs no filtering in this change (mirrors the existing `visitor-track-request` pattern of shipping visible-but-inert affordances).

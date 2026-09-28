## Context

The Audit Trail page (`src/presentation/pages/staff-audit-trail/`) currently reuses `DashboardSidebar` (the staff sidebar) and scopes its data to the signed-in staff member as host. The Admin portal has its own `AdminSidebar` (`src/presentation/components/AdminSidebar.tsx`) with a closed `AdminSidebarActiveItem` union and a `NAV_ITEMS`/`handleActivate` pair per item — the pattern every other admin page (`admin-dashboard`, `admin-roles`, etc.) follows.

The underlying data layer is already portal-agnostic: `GetAuditTrailUseCase`, `RequestAuditReportUseCase`, `GetAuditReportUseCase`, `DownloadAuditReportUseCase` (`src/data/use-cases/`), the `AuditTrailRepository` port, and `HttpAuditTrailRepository` (`src/infrastructure/audit-trail-repository.ts`) take filters and return results with no host-scoping built into the client — any host-scoping visible on the current staff page comes from filters/params passed in, not from the port's shape (per `.claude/rules/data-api-layer.md`, ports and adapters stay presentation-agnostic). Per proposal.md, `data/`, `domain/`, and `infrastructure/` are unaffected.

Per `.claude/rules/clean-architecture.md`, presentation never calls infrastructure directly — the admin-only check must be enforced in the page/hook using data already available through `useAppDependencies()` (the existing `GetCurrentStaffUserUseCase`, which returns `{ name, role, isAdmin }`), not by adding a new port.

No `ProtectedRoute`/`RequireAdmin` wrapper exists anywhere in `src/App.tsx` today — every route guard is done inline inside each page's hook (token-presence check, then redirect). This change follows that existing per-hook pattern rather than introducing route-level middleware, so it stays consistent with every other page in the app.

## Goals / Non-Goals

**Goals:**
- Move the Audit Trail experience from the staff portal to the Admin portal at `/admin/audit-trail`, admin-only.
- Reuse the existing audit-trail data layer (use cases, port, adapter, schemas) unchanged.
- Make the page show organisation-wide activity (drop the "signed-in staff member is the host" scoping used by the current page).

**Non-Goals:**
- No new generic route-guard/middleware mechanism (e.g. a `RequireAdmin` wrapper component) for the whole app — this change only gates the one new page, following the existing inline-hook-guard pattern. A reusable guard can be extracted later if a second admin-only page needs one.
- No backend/API changes — the `/audit-trail` and `/audit-trail/reports*` endpoints, and whether they already filter or return org-wide data, are unchanged; the frontend passes whatever filters it already supports.
- No change to permissions/roles data model — `isAdmin` on `StaffUser` already exists and is reused as-is.

## Decisions

**New page under `src/presentation/pages/admin-audit-trail/`, not a modified/renamed staff page.**
Mirrors how every other admin feature (`admin-dashboard`, `admin-roles`, …) has its own page directory with its own hook, distinct from any staff equivalent. The old `staff-audit-trail/` directory (page, hook, Components) is deleted outright rather than moved, since its host-scoped requirement no longer exists and its `DashboardSidebar` integration doesn't apply to the Admin portal.

**Admin-only gate implemented inline in `use-admin-audit-trail.ts`, matching the existing token-guard pattern.**
On mount: check `sessionStorage.getItem('token')` (redirect to `/admin/login` if absent, as every admin hook already does), then fetch the current user via `getCurrentStaffUserUseCase.execute()`. If `isAdmin` is `false`, redirect to `/staff/dashboard` immediately and skip fetching audit-trail data. This mirrors `use-admin-dashboard.ts`'s existing "fetch current user, then fetch page data" sequencing (`src/presentation/pages/admin-dashboard/hooks/use-admin-dashboard.ts:30-43`) with one added branch.
- *Alternative considered*: a shared `useRequireAdmin()` hook or a `<RequireAdmin>` route wrapper in `App.tsx`. Rejected for this change as unnecessary abstraction for a single call site — no other page needs role gating yet (per the rules file, "don't design for hypothetical future requirements"). If a second admin-only page is added later, this logic should be extracted then.
- *Alternative considered*: gate at the router level (`App.tsx`) before rendering the page component at all. Rejected because every existing guard (token and, now, role) reads from data only available after a hook runs (`sessionStorage`, an async `/me` fetch) — the router has no access to that without new shared state, and no other route does this today.

**Sidebar registration**: add `'audit-trail'` to `AdminSidebarActiveItem`, a `NAV_ITEMS` entry ("Audit Trail", reusing the existing `ClockIcon` used by the staff sidebar's audit-trail entry), and a `navigate('/admin/audit-trail')` branch in `handleActivate` — same shape as every existing item.

**Org-wide scoping is a filter/query concern, not a new port method.**
The current staff page's "hosted by me" scoping happens by filtering/deriving from the returned data in the hook layer (`use-staff-audit-trail.ts`), not the API contract. `use-admin-audit-trail.ts` calls the same `getAuditTrailUseCase.execute(filters)` without any host-narrowing, showing whatever the backend returns for the given date-range/activity-type/search filters. If the backend endpoint itself defaults to "current user's hosted visitors" server-side, that's a pre-existing backend behavior outside this change's scope (frontend-only, per proposal.md's Impact section) — flagged as an open question below.

## Risks / Trade-offs

- **Frontend-only admin gate is a UX guard, not a security boundary** → the redirect only prevents an unauthorized *view*; if the `/audit-trail` backend endpoint doesn't itself enforce admin-only access, a non-admin could still call it directly (outside the browser UI). This matches the existing `403` handling already built into `api-client.ts` (`handleAuthFailure`), which surfaces a permission error without forcing sign-out — so backend enforcement, if added, degrades gracefully on the frontend already. Enforcing that server-side is a backend concern, out of scope here.
- **Removing `/staff/audit-trail` is breaking for any staff member relying on it today** → accepted per explicit product decision (see proposal.md, "BREAKING"); no redirect/deprecation period requested.

## Open Questions

- Does the existing `/audit-trail` backend endpoint already scope results by "current user as host," independent of any frontend filter? If so, the admin page will need a backend change (or an explicit "all hosts" query param) to actually show organisation-wide data — this can be verified against the running API without changing this change's specs or task breakdown, since the frontend calls the port identically either way.

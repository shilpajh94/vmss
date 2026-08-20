## Context

See `proposal.md` - Why. This is the sixth Admin-section page, built on the same shell as `admin-branches`/`admin-departments`/`admin-buildings`/`admin-floors`/`admin-organisation-configs`:

- `AdminSidebar` (`src/presentation/components/AdminSidebar.tsx`) already defines a `'dashboard'` key in `AdminSidebarActiveItem` and renders the "Dashboard" nav item, but `handleActivate` has no case for it yet — this change adds that one line.
- `AdminTopBar` (`src/presentation/components/AdminTopBar.tsx`) is reused as-is with a Dashboard-specific `description`.
- Shared async-state conventions (`openspec/specs/async-ui-states/spec.md`, `openspec/specs/notifications/spec.md`) require `LoadingState`/`EmptyState` and the toast hook for any data-driven page — same pattern as every other admin page.
- No charting library is in `package.json` (`recharts`, `chart.js`, etc. are absent) and the project's existing components are all plain, dependency-free primitives (`ToastViewport`, `ToggleSwitch`, `Modal`). The Visitor Traffic chart is built the same way: a small in-repo SVG component, not a new dependency.
- The design (node `253:215`) has no destination for "View All" (Recent Check-ins), no branch-switching behavior for the branch selector, and no print flow for "Print Pass" — these stay inert, following the exact precedent of `admin-branches`' inert "Filters" control.
- `/staff/visitors/new` (`StaffVisitorRegistrationPage`) already exists and is what `staff-dashboard`'s "My actions" opens; "Pre-Register Visitor" reuses that same route rather than building a second registration entry point.

## Goals / Non-Goals

**Goals:**
- Implement the Dashboard overview exactly as designed (KPI row, traffic chart, recent check-ins, department breakdown, upcoming visitors), reusing the Admin shell.
- Make "Check In" on an upcoming visitor a real, working action, since it is the page's one clear write operation.
- Introduce one composed dashboard-overview read model so the page loads in a single fetch, rather than four or five separate list calls.

**Non-Goals:**
- No branch-switching behavior for the topbar's branch selector — it displays the current branch name only (see Risks).
- No global search behavior for the topbar's search field, and no destination page for "View All" — both inert, matching `admin-branches`' "Filters" precedent.
- No pagination, sorting, or filtering on Recent Check-ins or Upcoming Pre-Registered Visitors — the backend response is rendered as returned, same flat-list approach as every other admin list page.
- No "Print Pass" implementation — no printing infrastructure exists anywhere in the codebase; the button stays inert until a print flow is designed.

## Decisions

- **One composed `GET /admin/dashboard/overview` endpoint backing the whole page, instead of five separate calls.** The page is a single read-only view; the KPIs, chart series, recent check-ins, department breakdown, and upcoming visitors all refresh together and have no independent loading/error state in the design. A single `DashboardOverviewSchema` (`kpis`, `trafficSeries`, `recentCheckins`, `departmentBreakdown`, `upcomingVisitors`) keeps the hook's loading/error state as simple as `staff-dashboard`'s single-list load. If the backend later needs these to refresh independently, splitting the endpoint is a backend-and-adapter-only change; the spec's scenarios (all keyed off "the overview data loads") do not need to change for a single-endpoint implementation to satisfy them.
- **KPI trend captions and direction come from the backend as data, not computed client-side.** The four captions in the design aren't a uniform format ("+12% from average", "Active badge passes", "Awaiting check-in", "-5m from yesterday") — two are percentage comparisons, two are static labels. Rather than encode that heterogeneity into client logic, each KPI carries `{ label, value, trendCaption, trendDirection: 'up' | 'down' }` and the client only picks the up/down icon from `trendDirection`.
- **Custom lightweight SVG line/area chart component, not a charting library.** Matches the project's existing "no new dependency for one visual" pattern (see `admin-branches` design's Modal/ConfirmDialog decision). The component takes `{ points: { label: string; value: number }[] }` and computes its own scale/path — no interactivity beyond the design's single tooltip-on-hover, which is out of scope for this pass (static chart, no hover tooltip).
- **Department breakdown bar colors cycle through existing theme tokens (`admin-accent`, `secondary-accent`, `info`, `text-faint`, …) by index, not new tokens.** The design shows a different color per bar, but none of the five hex values map cleanly to a single existing token the way `admin-branches`' status badges did; adding five new one-off tokens for a single list would grow the token set for a purely decorative distinction. Cycling existing tokens keeps the visual variety without new tokens.
- **Check-in mutates via a dedicated `PATCH /admin/dashboard/upcoming-visitors` call, id passed as a query parameter.** Follows the same `ApiClient`/`API_ENDPOINTS` fixed-path convention `UPDATE_BRANCH`/`DELETE_BRANCH` already use (no path-templating in `ApiClient`); the response returns nothing beyond success, so the hook removes the visitor from local state by id rather than merging a returned record.
- **Recent Check-ins' status badge is a new two-value enum (`'checked-in' | 'checked-out'`) distinct from `staff-dashboard`'s four-value visit-request status.** These are different read models — this page's check-ins are a historical log entry, not an actionable kanban card — so reusing `staff-dashboard`'s status type would force an awkward subset/superset relationship for no shared behavior.

## Risks / Trade-offs

- [Single aggregate endpoint invented ahead of a real backend contract] → If the backend instead exposes these as separate resources, only the infrastructure adapter and composition-root wiring change; the domain schema, use case shape, and spec scenarios stay valid since they're keyed off "the overview data," not a specific endpoint count.
- [Custom SVG chart is a simplified approximation of the Figma area+line chart, with no hover tooltip] → Acceptable for this pass given no charting dependency exists in the project; a tooltip or richer interaction can be layered on later without changing the data contract.
- [Branch selector and search stay non-functional] → Matches multiple existing precedents (`admin-branches` Filters, `staff-dashboard` Filters); revisit once a multi-branch admin workflow or global search feature is actually scoped.

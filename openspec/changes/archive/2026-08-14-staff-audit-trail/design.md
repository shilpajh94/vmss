## Context

See proposal.md - Why. The Audit Trail page is pixel-matched to Figma node `62:1532` ("host-audit-trail"), which reuses the same dark sidebar and workspace-header shell already shipped for `staff-dashboard` and `staff-visitor-registration`.

Relevant existing state:
- `DashboardSidebar` (`src/presentation/components/DashboardSidebar.tsx`) already accepts `activeItem: 'all-visitors' | 'my-actions' | 'audit-trail'` and already applies active styling for `'audit-trail'`, but its `handleActivate` has no navigation branch for it yet.
- The staff auth-guard pattern (`sessionStorage.getItem('token')` check, redirect to `/staff/login`) and the workspace-header identity pattern (avatar/initials, name, role via `getCurrentStaffUserUseCase`, divider, sign-out) exist in `staff-dashboard` but are page-local, not shared components — each staff page (dashboard, visitor-registration) re-implements its own header. This page follows that established convention rather than extracting a new shared component, to avoid an unplanned refactor of the existing pages.
- `API_ENDPOINTS` has no pagination/filter envelope precedent: `LIST_VISIT_REQUESTS` returns a bare array and the dashboard board filters/searches entirely client-side over that array.
- No stat-card, filter-dropdown, data-table, or pagination component exists anywhere in `src/presentation/components/` or any page's `Components/` folder.

## Goals / Non-Goals

**Goals:**
- Render the Audit Trail page pixel-matched to the Figma design, wired into the existing staff shell and routing conventions.
- Fix the dead "Audit trail" sidebar nav item.
- Establish a clean, reusable pattern (stat card, filter-dropdown, activity table with status pill, pagination control) as page-local components, following the project's "page-local first, promote later" convention already used for `staff-visitor-registration`'s step components.

**Non-Goals:**
- Extracting the workspace header or auth-guard into a shared component (out of scope; both existing staff pages would need a follow-up refactor).
- Server-side sorting or column customization — not present in the Figma design.
- Exporting or printing the activity log.

## Decisions

**New endpoint returns the full filtered/paginated result in one call.** `API_ENDPOINTS.LIST_AUDIT_TRAIL` (`GET /staff/audit-trail`, `hasToken: true`) accepts `queryParams` for `dateRange`, `activityType`, `search`, `page`, and `pageSize`, and returns `{ items: AuditLogEntry[], total: number, stats: AuditTrailStats }` in one response, validated by a single `AuditTrailResponseSchema`. Alternative considered: fetch all entries once (like `LIST_VISIT_REQUESTS`) and filter/paginate client-side — rejected because the Figma shows 481 total results and the existing dashboard-board client-filter pattern assumes a small, fully-loaded list; re-fetching per filter/page change keeps payload size bounded as the audit log grows without inventing a second, inconsistent data-fetch pattern later.

**Filter and page state live in the page's own hook, refetching on change.** `use-staff-audit-trail.ts` holds `{ dateRange, activityType, search, page }` state and calls `getAuditTrailUseCase.execute(filters)` whenever it changes (debounced for `search`), mirroring `use-staff-dashboard.ts`'s existing fetch-and-set-state shape.

**Stats come from the same response as the current filtered range, not a separate global-stats call.** The Figma has no visible interaction cue distinguishing "stats for all time" from "stats for the active filters", and a single endpoint avoids a second round-trip. Alternative considered: a separate always-unfiltered stats endpoint — deferred; if product feedback wants stats independent of filters, that's a small additive follow-up (new query behavior, not a breaking one).

**New page-local components, not shared ones, mirroring `staff-visitor-registration`'s Components/ folder convention:** `Components/SummaryStatCard.tsx`, `Components/AuditFilterBar.tsx` (composing a small internal `DropdownFilter` for date-range/activity-type), `Components/ActivityTable.tsx`, `Components/StatusPill.tsx`, `Components/Pagination.tsx`. If a later page needs the same pieces, promote then — consistent with this repo's existing pattern of promoting `DashboardSidebar` only once a second consumer needed it.

**Status pill colors extend the theme's existing semantic tokens.** `Approved`/`Completed`(-adjacent success) → `--color-success`, `Rejected`/`Flagged` → `--color-danger`. The Figma's "Modified" orange (`#f97316`) and "Completed" neutral gray (`#e5e7eb` bg / `#64748b` text) have no existing token; add `--color-modified` and reuse `--color-text-muted`/a new `--color-neutral-subtle` in `src/styles/theme.css` rather than hardcoding hex in the component, keeping the "Tailwind v4 + `@theme` tokens" convention intact.

## Risks / Trade-offs

- [Refetching on every filter change adds request volume vs. a client-filtered small list] → Debounce the search input (as the visitor-request wizard already debounces elsewhere) and keep page size fixed at 8 (matching the Figma's "1-8 of 481") so each request stays cheap.
- [New response envelope (`items`/`total`/`stats`) is a new shape not seen elsewhere in `data/api`] → Documented as an explicit design decision above; future paginated staff endpoints should follow the same envelope for consistency.
- [No shared workspace-header/auth-guard component means a third near-duplicate implementation] → Acceptable per Non-Goals; flag for a future dedicated refactor change once a fourth staff page would otherwise duplicate it again.

## Migration Plan

Additive only: a new route, a new capability, and one new sidebar navigation branch. No existing data or endpoints change shape. Nothing to migrate or roll back beyond reverting the new files and the one sidebar edit.

## Context

See `proposal.md` - Why. This builds directly on `admin-organisation-configs` (the first Admin-section page):

- `AdminSidebar` (`src/presentation/components/AdminSidebar.tsx`) already defines a `'branches'` key in its `AdminSidebarActiveItem` union and already renders the "Branches" nav item — it is reused as-is, just activated with `activeItem="branches"`.
- The admin top bar currently lives as a page-local `TopBar` inside `admin-organisation-configs/Components/TopBar.tsx`, hardcoding the description text. This change needs the same top bar shape with a different description, so it is promoted to a shared `AdminTopBar` (title fixed, `description` and `currentUser` as props) under `src/presentation/components/`, and `admin-organisation-configs` is switched to use it.
- Shared async-state conventions (`openspec/specs/async-ui-states/spec.md`, `openspec/specs/notifications/spec.md`) require the shared `LoadingState`/`EmptyState` components and the toast hook for any list-driven page — this page follows the same pattern already used by `staff-dashboard` and `admin-organisation-configs`.
- No `Modal`/`Dialog` component exists anywhere in `src/presentation/components/ui/`. The Figma design only covers the list view (node `203:148`); there is no form or confirmation dialog design to follow.
- Existing icons already cover every affordance this page needs: `PlusIcon`, `PencilIcon`, `TrashIcon`, `SlidersIcon` (Filters) are already defined in `src/presentation/components/icons.tsx` from earlier work — no new icons are needed.

## Goals / Non-Goals

**Goals:**
- Implement the Branches Register list exactly as designed (table columns, Active/Inactive badge, row actions), reusing the Admin shell from `admin-organisation-configs`.
- Implement full CRUD (add/edit/delete) since the page's core purpose is managing branches, using a plain form built from existing primitives (`TextField`, `ToggleSwitch`) rather than blocking on a form design that doesn't exist.
- Introduce `Modal` and `ConfirmDialog` as shared, reusable primitives so the next CRUD-shaped admin page (Departments, Buildings, ...) doesn't have to invent its own.

**Non-Goals:**
- No pagination, sorting, or column filtering for the branch table — the Figma design shows a flat list and "Filters" stays inert, matching the same pattern used on Staff dashboard/audit-trail and `admin-organisation-configs`.
- No branch detail/drill-down page — row actions are limited to Edit and Delete per the design.
- No change to `admin-organisation-configs`'s observable behavior — the `AdminTopBar` extraction is a pure refactor (see Decisions).

## Decisions

- **Promote `TopBar` to shared `AdminTopBar` instead of duplicating it.** Both admin pages need an identical top bar shape (title, search/notification affordances, profile) differing only in the description line. Duplicating the whole component for a one-line copy difference would immediately diverge; a `description: string` prop keeps both pages in sync structurally. This is a refactor, not a behavior change — `admin-organisation-configs`'s spec requirements (title, description text, inert search/notification, profile display) are unchanged, so no delta spec is filed for that capability.
- **New `Modal` + `ConfirmDialog` shared primitives, built plainly (no animation library, no portal dependency beyond React's own DOM APIs).** Consistent with the project's existing minimal, dependency-free component style (see `ToastViewport`, `ToggleSwitch`). `Modal` takes `{ isOpen, onClose, title, children }`; `ConfirmDialog` wraps it with `{ isOpen, title, message, confirmLabel, onConfirm, onCancel }` for the delete flow.
- **One `BranchFormModal` component serves both Add and Edit.** The only difference between the two flows is whether the form starts empty or pre-filled and which use case `save` calls; sharing the form avoids duplicating field markup and client-side validation.
- **Required-field validation is client-side only, checked on submit.** `Branch` name/location/branchCode/contactPerson are required per the spec; the form blocks submission and shows inline errors using the same `error` prop pattern `TextField`/`SelectField` already support. Status is not required-validated since it's a toggle with a default.
- **Status modeled as a boolean-backed toggle, not a select.** The Figma table shows a two-state Active/Inactive badge, matching the existing `ToggleSwitch` (introduced in `admin-organisation-configs`) better than a two-option `SelectField`. `BranchSchema.status` is still the string enum `'active' | 'inactive'` for the wire contract; the form maps the toggle's boolean to that enum.
- **Optimistic list update, not a full refetch, after create/update/delete.** `create`/`update` responses return the full `Branch` record, so the hook merges it into local state directly; `delete` removes the row by id. This avoids an extra round-trip after every mutation, matching the responsiveness implied by the "closes the form" / "removes it from the table" scenarios.
- **Branch id addressing via query parameter, not a path segment.** The existing `API_ENDPOINTS`/`ApiClient` pattern (`.claude/rules/data-api-layer.md`) has no path-templating mechanism — every endpoint is a fixed string. Rather than extend `ApiClient` for this one case, `UPDATE_BRANCH`/`DELETE_BRANCH` reuse the fixed `/branches` path and pass `id` as a query parameter (the same mechanism `LIST_AUDIT_TRAIL` already uses for its filters), avoiding a change to the shared HTTP client for a single call site.
- **Active-badge styling uses existing theme tokens at reduced opacity (`bg-success/15 text-success`) rather than new tokens.** The Figma hex pair (`#d1fae5`/`#065f46`) doesn't have a matching pre-existing pair in `theme.css`; reusing `--color-success` via Tailwind's opacity modifier keeps the badge on-brand without growing the token set for one badge. The Inactive badge reuses `--color-border-subtle`/`--color-text-muted`, which already visually match Figma's inactive pair.

## Risks / Trade-offs

- [No design for the add/edit form] → Built plainly from existing primitives per explicit user direction; if a Figma form design appears later, `BranchFormModal`'s internals can be restyled without touching the CRUD flow, use cases, or schema.
- [Branch id via query parameter instead of a REST path segment] → Diverges from typical REST convention, but avoids widening `ApiClient`'s contract for one endpoint pair; revisit if more path-addressed resources appear (a good trigger to add real path-param support to `ApiClient` instead of repeating this workaround).
- [Optimistic local updates after mutations] → If the backend applies side effects beyond what the response body reflects, the table could show slightly stale data until the next full page load; acceptable given the page has an explicit retry-on-failure path and no polling requirement.

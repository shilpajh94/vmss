## Context

See `proposal.md` - Why. This revises `admin-branches` (implemented and archived in `2026-08-18-admin-branches`), built without the real Figma design for creating a branch (node `206:4`). Relevant existing state:

- `Branch`/`BranchSchema` (`src/domain/entities/branch-schema.ts`): `id`, `name`, `locationCity`, `branchCode`, `contactPerson`, `status`.
- `BranchRepository`/use cases (`create`, `update`, `remove`, `list`) already pass a full `Branch` (minus `id`) to `create`/`update` and return a full `Branch` — widening the schema requires no change to the port, adapter, or use cases.
- `BranchFormModal` currently drives both add and edit from `admin-branches.tsx`; `use-admin-branches.ts` holds `formState: { mode: 'add' } | { mode: 'edit'; branch }`.
- `AdminTopBar` (`src/presentation/components/AdminTopBar.tsx`) currently renders a fixed title ("Organization Admin") plus a `description` string on the left, and a fixed search/notification/profile cluster on the right.
- The user confirmed (see conversation): Add moves to a full page, Edit stays a modal with the same expanded fields; Country and Operating Hours become hardcoded-option `SelectField`s, Contact Person stays free text (no employee directory exists).

## Goals / Non-Goals

**Goals:**
- Match the Figma create-branch page (node `206:4`) layout, sections, fields, and footer actions.
- Widen `Branch` to carry every field the design collects, without breaking the existing list/table view (which shows only name, location/city, branch code, contact person, status).
- Keep Edit working via the existing modal, now with the same field set as create, so nothing an admin can set on creation becomes unreachable when editing.

**Non-Goals:**
- No employee directory, country-list, or scheduling backend — Contact Person is free text; Country and Operating Hours use hardcoded option lists (same pattern as Timezone in `admin-organisation-configs`).
- No Figma design for the edit flow — the edit modal is expanded pragmatically, not pixel-matched to anything.
- No pagination/filtering changes to the Branches list — out of scope, unchanged from the prior change.

## Decisions

- **`AdminTopBar` gains a breadcrumb mode instead of a new component.** The create page's top bar differs from the existing title/description top bar only on the left side (a breadcrumb trail vs. a title+description pair) — the right side (search, notification, profile) is identical. Rather than duplicate the whole shell for that, `AdminTopBar` now accepts either `description: string` (existing pages) or `breadcrumb: { label: string; isActive?: boolean }[]` (new), rendering one or the other on the left. Alternative considered: a separate `AdminBreadcrumbTopBar` component — rejected as needless duplication of the identical right-hand markup for a one-sided difference, and this shape will likely recur for other "create X" admin pages.
- **Widen `BranchSchema` in place rather than versioning it.** No versioning mechanism exists elsewhere in this codebase's schemas, and the feature was never shipped to a real backend (this change assumes the backend accepts the new shape, consistent with how `admin-branches` was proposed). New required fields: `country`, `physicalAddress`, `contactEmail`, `contactPhone`. New optional fields: `operatingHoursFrom`, `operatingHoursTo`, `notes`.
- **Create page is a new page + hook, not a reused `BranchFormModal` instance rendered inline.** A full page has its own breadcrumb top bar, its own header/description, and navigates on success/cancel — different enough from a modal's lifecycle (open/close, backdrop) that forcing the existing modal component to also render "modeless" would complicate it for both call sites. `BranchFormModal` keeps serving Edit only; the create page owns its own field markup, sharing the same primitives (`TextField`, `TextareaField`, `SelectField`, `ToggleSwitch`).
- **`use-admin-branches.ts` drops `add` from its `BranchFormState` union.** Since creation no longer happens on the Branches list page, the hook's form state becomes `{ mode: 'edit'; branch: Branch } | undefined`; "Add Branch" becomes a plain `navigate('/admin/branches/new')` call in the page component.
- **New `use-admin-branch-create.ts` hook owns the create page's form state and submission.** On success it navigates to `/admin/branches` (the list re-fetches on mount, so the new branch appears via the existing load path — no need to pass state between routes) and fires the success toast there; on failure it fires an error toast and keeps the admin on the page with their entered values untouched, matching the spec's "remains on the create page" requirement.
- **Country and Operating Hours option lists are small, illustrative sets**, matching the Timezone precedent: Country gets a short list of countries (with "United Kingdom" first, matching the Figma placeholder), Operating Hours gets hourly increments in `hh:mm AM/PM` format from 6:00 AM to 10:00 PM.
- **Operational Status keeps the existing `active`/`inactive` enum and `ToggleSwitch`** — the Figma label "Active / Open" is cosmetic copy for this page; the underlying value and list-page badge are unchanged.

## Risks / Trade-offs

- [Contact Person stays free text despite the Figma dropdown chevron] → Acceptable per explicit user direction; once Host Employees ships a real directory, this field can become a `SelectField` without changing the schema (`contactPerson` stays a string, just populated from a list instead of typed).
- [`AdminTopBar`'s two modes add a small branch in one shared component] → Kept to a single optional prop pair rather than two components; if a third top-bar shape appears, revisit whether a composable slot-based API is warranted instead of a third mode.
- [Edit modal's field set now has no Figma reference] → Internal-only risk; can be restyled later without touching the schema, use cases, or the create page.

## Context

See `proposal.md` - Why. This is the third Admin-section page, building on `admin-organisation-configs` and `admin-branches`:

- `AdminSidebar` already declares `'departments'` in `AdminSidebarActiveItem` and renders the "Departments" nav item, but `handleActivate` has no case for it yet — only `organisation-configs` and `branches` navigate.
- `AdminTopBar`, `Modal`, `ConfirmDialog`, `LoadingState`, `EmptyState`, `TextField`, `SelectField`, `TextareaField`, `ToggleSwitch` are all established shared primitives from the prior two changes; this page introduces no new shared UI.
- `admin-branches` already exposes `listBranchesUseCase` on `AppDependencies` — this is the first change to consume another Admin capability's use case from a different page, rather than just its shared UI.
- Figma provides both designs this time: the list (node `203:307`) and the Add Department page (node `217:5`, back-button + form card, using the same description-mode top bar as the list — no breadcrumb, unlike `admin-branches`'s create page).

## Goals / Non-Goals

**Goals:**
- Match both Figma designs (list and Add Department) pixel-for-pixel.
- Reuse the existing Branches data for the Branch dropdown — the first real inter-capability data dependency in the Admin section.
- Ship full CRUD from the start, since both a list and an add design exist and the user confirmed Edit/Delete should be wired up too.

**Non-Goals:**
- No employee directory — Head of Department stays free text, same rationale as `admin-branches`'s Contact Person.
- No department detail/drill-down page beyond edit.
- No change to how Employee Count is computed — it is read from the department record as returned by the backend and never edited.

## Decisions

- **One page component serves both Add and Edit**, routed as `/admin/departments/new` and `/admin/departments/:id/edit`. Unlike `admin-branches` (where Edit stayed a modal because Add became a page with a *different* top-bar treatment — breadcrumb vs. description), Departments' Add page already uses the same description-mode top bar as the list, plus a plain back button in the content area. That symmetry means Edit can reuse the identical page shell with no new top-bar mode, so a second modal component isn't worth building. The page's hook reads a `:id` route param; when present, it loads that department first and pre-fills the form, and submission calls `update` instead of `create`.
- **Branch dropdown fetches from `listBranchesUseCase`, not a hardcoded list.** This is the first cross-capability data reuse in the Admin section — Departments' create/edit form loads the real branch list on mount and renders it as `SelectField` options (`value` = branch id, `label` = branch name). If the branch list fails to load, the form still renders with an empty Branch dropdown and its own inline error, independent of the department's own load/save state.
- **`DepartmentSchema` separates the stored record from the create/edit input.** The record includes `branchName` and `employeeCount`, both backend-supplied/denormalized for display in the list table; the create/edit payload only sends `name`, `branchId`, `headOfDepartment`, `description`, `status` — never `branchName` or `employeeCount`, since the admin doesn't set either. This mirrors why `admin-branches` never asks the admin to type a status badge color: some fields are server-owned display data, not form input.
- **Head of Department is free text**, matching the `admin-branches` Contact Person precedent, for the same reason (no employee directory yet). It's optional per the Figma design (no required-field asterisk), unlike Branch which is required.
- **`AdminSidebar.handleActivate` gains a `departments` case.** This is a one-line addition to existing dead code (the key already existed but did nothing) — no new sidebar API.
- **Employee Count is rendered read-only in the list; it never appears in the Add/Edit form.** The Figma form has no field for it, confirming it's system-computed (presumably from actual employee-to-department assignments, which don't exist as a capability yet).

## Risks / Trade-offs

- [Head of Department stays free text despite the Figma dropdown chevron] → Same acceptable trade-off as `admin-branches`'s Contact Person; becomes a real picker once Host Employees ships.
- [Branch dropdown depends on `admin-branches`'s use case] → A real coupling between two Admin capabilities' data layers (via the composition root, not via UI imports) — acceptable since both live in the same Admin section and share a backend; if Branches's shape changes, Departments' Branch dropdown must be updated too.
- [One page for Add and Edit] → If a future Figma design diverges between adding and editing a department, this will need splitting; low risk today since no such design exists.

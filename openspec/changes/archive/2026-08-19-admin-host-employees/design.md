## Context

See `proposal.md` - Why. This is the sixth Admin CRUD page, built on the same shell and conventions as `admin-branches`/`admin-departments`/`admin-buildings`/`admin-floors`:

- `AdminSidebar` already defines a `'host-employees'` key in `AdminSidebarActiveItem` and renders the "Host Employees" nav item with `UserCheckIcon`, but `handleActivate` has no case for it yet — this change adds that one line, following the exact precedent of the `admin-dashboard` change wiring `'dashboard'`.
- `AdminTopBar` is reused as-is with a Host-Employees-specific `description`.
- The most recent CRUD pages (`admin-departments`, `admin-buildings`, `admin-floors`) all use a dedicated create/edit route (`/admin/<capability>/new`, `/admin/<capability>/:id/edit`) sharing one form page component for both modes, rather than `admin-branches`' original modal. This change follows that newer, now-established pattern rather than reintroducing a modal.
- Per user decision (see conversation), the design's only header action, "Import Hosts", stays inert for this pass — no CSV upload/parsing pipeline is built. A dedicated "Add Host Employee" create page is added instead, matching every other admin CRUD page's affordance for manual entry.
- `Department` (`src/domain/entities/department-schema.ts`) already carries `branchId`/`branchName` denormalized from its own branch. Host employees are modeled the same way through their department, rather than picking a branch independently (see Decisions).

## Goals / Non-Goals

**Goals:**
- Implement the Host Employees Directory list exactly as designed (table columns, role/access badge, status badge, row actions), reusing the Admin shell.
- Implement full CRUD (add/edit/delete) via a dedicated create/edit page, consistent with the newer admin-page pattern.

**Non-Goals:**
- No CSV/bulk import — "Import Hosts" stays inert, per explicit user direction. Revisit if a real bulk-onboarding need is scoped later.
- No independent branch selection on the form — branch is derived from the selected department and shown read-only, since `Department` is already branch-scoped and letting the two disagree would create an inconsistent record.
- No pagination, sorting, or column filtering — "Filters" stays inert, matching every prior admin list page.
- No host-employee detail/drill-down page — row actions are limited to Edit and Delete per the design.

## Decisions

- **`HostEmployee` carries `departmentId` plus denormalized `departmentName` and `branchName`, not a separate `branchId`.** The Figma table shows both a Department and a Branch column, but every existing `Department` already belongs to exactly one branch. Adding an independent branch field to `HostEmployee` would let an admin pick a department and a branch that don't agree, with no clear resolution rule. Deriving branch from the selected department keeps the data consistent and mirrors how `Department` itself denormalizes `branchName` from `branchId`.
- **Role/access modeled as a fixed three-value enum: `'host' | 'security-admin' | 'system-admin'`.** These are the only three values shown across the design's four example rows; no fourth value or free-text option appears anywhere in the file. `HostEmployeesTable` maps each value to a distinct badge color (danger for Security Admin, admin-accent for Host, info for System Admin) purely for visual distinction, reusing existing theme tokens rather than adding new ones.
- **Dedicated create/edit page (`AdminHostEmployeeFormPage`), not a modal.** Matches `admin-departments`/`admin-buildings`/`admin-floors` — the more recent, now-established pattern — rather than `admin-branches`' original `Modal`-based form. One component serves both Add and Edit, switching on whether a route `:id` param is present, exactly like `AdminDepartmentFormPage`.
- **Required-field validation is client-side only, checked on submit.** Name, department, email, and role/access are required per the spec; status defaults to `'active'` and is a toggle, not required-validated — same approach as `admin-departments`.
- **Host employee id addressing via query parameter on update/delete, not a path segment.** Follows the same `ApiClient`/`API_ENDPOINTS` fixed-path convention every other admin CRUD capability already uses.
- **"Import Hosts" renders as a disabled-looking but still-visible button with no click behavior**, the same treatment `admin-branches`/`admin-departments` give "Filters" — present per the design, inert on activation.

## Risks / Trade-offs

- [Branch not independently editable on the host-employee form] → If a future requirement needs a host employee attached to a branch different from their department's branch, this needs a real design decision (e.g. an explicit branch override field) rather than silently diverging from the department's branch; flag this if it comes up.
- ["Import Hosts" stays inert] → An admin has no bulk-onboarding path yet, only one-at-a-time create; acceptable per explicit user direction, revisit when CSV import is actually scoped with a real upload/parsing design.
- [Role/access is a closed three-value enum inferred from four example rows] → If the backend actually supports more roles, this need only widen the enum and the badge-color map — no shape change to the rest of the page.

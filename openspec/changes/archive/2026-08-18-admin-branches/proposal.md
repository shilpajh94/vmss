## Why

The Admin section (added by `admin-organisation-configs`) needs its "Branches" screen — a Super Admin's register of the organisation's geographical branches. The list layout is fully specified in Figma (node `203:148`); the design has no separate screen for adding or editing a branch, but the page's whole purpose is managing branches, so "Add Branch", row edit, and row delete need to be real functionality rather than placeholders.

## What Changes

- Add the **Branches** page (`/admin/branches`) rendering the Admin shell (existing `AdminSidebar` with "Branches" active, existing admin top bar) and a "Branches Register" table matching the Figma design: Branch Name, Location/City, Branch Code, Contact Person, Status (Active/Inactive badge), and row actions (Edit, Delete).
- Add full CRUD for branches, since no Figma form design exists to follow: "Add Branch" and row "Edit" open a modal form (name, location/city, branch code, contact person, active/inactive) built from the project's existing form primitives; row "Delete" opens a confirmation dialog before removing the branch.
- Add two new shared UI primitives needed for this: `Modal` (a generic dialog shell) and a `ConfirmDialog` built on it — no modal/dialog component exists yet.
- Show the shared `LoadingState` while the list loads, the shared `EmptyState` when there are zero branches, and inline error-with-retry plus an error toast when the list fails to load, matching the async-ui-states and notifications capabilities already established.
- The "Filters" affordance is presented per the design but stays inert, matching the same "visible but not yet functional" pattern already used elsewhere in the Admin and Staff sections.
- **Refactor (no behavior change)**: extract the admin top bar out of `admin-organisation-configs`'s page-local `TopBar` into a shared `AdminTopBar` component (title fixed, `description` now a prop) so the Branches page can reuse it with its own subtitle. This does not change `admin-organisation-configs`'s observable behavior, so no delta spec is needed for that capability.

## Capabilities

### New Capabilities
- `admin-branches`: the Branches Register page — listing branches, and adding, editing, and deleting a branch.

### Modified Capabilities
_None — `admin-organisation-configs`'s top bar is refactored for reuse, but its requirements (title, description, search/notification/profile affordances) are unchanged._

## Impact

- **New route**: `/admin/branches` in `src/App.tsx`.
- **New presentation code**: `src/presentation/components/ui/Modal.tsx`, `src/presentation/components/ui/ConfirmDialog.tsx`, `src/presentation/components/AdminTopBar.tsx` (promoted from `admin-organisation-configs`'s page-local `TopBar`), `src/presentation/pages/admin-branches/` (page, hook, components).
- **Changed presentation code**: `src/presentation/pages/admin-organisation-configs/admin-organisation-configs.tsx` switches from its local `TopBar` to the new shared `AdminTopBar`; the page-local `TopBar.tsx` is removed.
- **New domain schema**: `src/domain/entities/branch-schema.ts`.
- **New data layer**: `src/data/repositories/branch-repository.ts` (port), `src/data/use-cases/list-branches.ts`, `src/data/use-cases/create-branch.ts`, `src/data/use-cases/update-branch.ts`, `src/data/use-cases/delete-branch.ts`.
- **New infrastructure**: `src/infrastructure/branch-repository.ts` (adapter), new entries in `src/data/api/api-endpoints.ts` (`LIST_BRANCHES`, `CREATE_BRANCH`, `UPDATE_BRANCH`, `DELETE_BRANCH`).
- **Composition root**: `src/composition-root.ts` gains `branchRepository`, `listBranchesUseCase`, `createBranchUseCase`, `updateBranchUseCase`, `deleteBranchUseCase` on `AppDependencies`.
- **No backend changes are made by this change** — it assumes the four new endpoints exist; exact request/response shapes are defined in the new domain schema.

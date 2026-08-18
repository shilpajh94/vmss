## Why

The Admin section needs its "Buildings" screen, per Figma: a list (node `203:553`, "Buildings Registry") and a dedicated Add/Edit Building page (node `218:66`). Unlike the flat forms in `admin-branches`/`admin-departments`, the Add Building page manages a nested structure — a building has Floors, and each Floor has its own Security Checkpoints — confirmed in scope as full nested CRUD.

## What Changes

- Add the **Buildings** page (`/admin/buildings`) rendering the Admin shell (`AdminSidebar` with "Buildings" active, `AdminTopBar` in description mode) and a "Buildings Registry" table matching the Figma design: Building Name, Branch, Address, Total Floors, Reception Desks, Status (Active/Inactive badge), and row actions (Edit, Delete).
- Add the **Add/Edit Building** page (`/admin/buildings/new` and `/admin/buildings/:id/edit`) matching Figma node `218:66`: a back button + "Add Building"/"Edit Building" header, a form card with a "Building Details" section (Building Name, Branch — a real dropdown populated from the existing Branches list, Street Address, Building Status toggle) and a "Floors" section (Add Floor; each floor card expands/collapses to reveal its Security Checkpoints list with Add/Edit/Delete), and Cancel/Save Building footer actions. One page serves both Add and Edit, mirroring `admin-departments`.
- Floors and their Checkpoints are part of the Building's own data — added, renamed, and removed entirely client-side (local form state) and only persisted when "Save Building" is submitted, not through separate endpoints. Add/Edit Floor and Add/Edit Checkpoint each open a small modal (built on the existing `Modal`) with just a name field, since no design exists for those sub-forms beyond the plain floor/checkpoint name shown in the list rows.
- Deleting a floor or a checkpoint (from within the form) and deleting a building (from the list) all reuse the existing `ConfirmDialog`.
- The Branch dropdown reuses the existing `listBranchesUseCase`, matching the cross-capability pattern established by `admin-departments`.
- "Total Floors" is derived from the floors array's length, not a separately submitted field. "Reception Desks" is a read-only, backend-supplied display value shown in the list only (no reception-desk capability exists yet) — the same treatment `admin-departments` gives Employee Count.
- "Filters" is presented per the design but stays inert, matching the established pattern.
- Wires the `AdminSidebar`'s existing "Buildings" nav item (key and label already exist, but `handleActivate` has no case for it) to navigate to `/admin/buildings`.

## Capabilities

### New Capabilities
- `admin-buildings`: the Buildings Registry page and the Add/Edit Building page — listing buildings, and adding, editing, and deleting a building along with its nested floors and security checkpoints.

## Impact

- **New routes**: `/admin/buildings`, `/admin/buildings/new`, `/admin/buildings/:id/edit` in `src/App.tsx`.
- **Changed presentation code**: `AdminSidebar.tsx`'s `handleActivate` gains a `buildings` case that navigates to `/admin/buildings`.
- **New presentation code**: `src/presentation/pages/admin-buildings/` (list page, form page, floor/checkpoint modal components, hooks).
- **New domain schema**: `src/domain/entities/building-schema.ts` (Building, Floor, Checkpoint).
- **New data layer**: `src/data/repositories/building-repository.ts` (port), `src/data/use-cases/list-buildings.ts`, `src/data/use-cases/create-building.ts`, `src/data/use-cases/update-building.ts`, `src/data/use-cases/delete-building.ts`.
- **New infrastructure**: `src/infrastructure/building-repository.ts` (adapter), new entries in `src/data/api/api-endpoints.ts` (`LIST_BUILDINGS`, `CREATE_BUILDING`, `UPDATE_BUILDING`, `DELETE_BUILDING`).
- **Composition root**: `src/composition-root.ts` gains `buildingRepository`, `listBuildingsUseCase`, `createBuildingUseCase`, `updateBuildingUseCase`, `deleteBuildingUseCase` on `AppDependencies`.
- **No change** to `admin-branches` — its `listBranchesUseCase` is consumed as-is by the new Branch dropdown.
- **No backend changes are made by this change** — it assumes the four new endpoints exist and accept/return a building with its nested floors and checkpoints; exact shape is defined in the new domain schema.

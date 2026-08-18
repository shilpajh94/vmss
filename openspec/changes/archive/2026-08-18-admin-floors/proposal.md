## Why

The Admin section needs its "Floors" screen, per Figma: a global "Floors Inventory" registry (node `203:647`) listing every floor across every building, with richer per-floor data (building, department(s), capacity, access level, status) than the simple name-only floor tracked inside `admin-buildings`. No Add/Edit Floor form design exists. The user confirmed: extend the existing `Floor` entity (one source of truth, no drift between this registry and the Buildings form) and ship full CRUD.

## What Changes

- Widen the `Floor` entity (currently `{ id, name, checkpoints }`, nested inside a Building's `floors` array) with `capacityCount`, `capacityUnit` (`'Guests' | 'Staff'`), `accessLevel` (`'public' | 'restricted' | 'secure'`), `departmentIds` (references into `admin-departments`), and its own `status` (`'active' | 'inactive'`, independent of the parent building's status). No new endpoints or entities — a floor is still persisted only as part of its parent Building's `floors` array via the existing `updateBuildingUseCase`.
- Add the **Floors** page (`/admin/floors`): a "Floors Inventory" table (Floor Name/Number, Building, Department(s), Capacity, Access Level, Status, Actions) matching the Figma design. Its data is derived client-side by loading every building (`listBuildingsUseCase`) and flattening their `floors` arrays, denormalizing each floor with its parent building's id/name; department names are resolved by loading the department list (`listDepartmentsUseCase`) and looking up each floor's `departmentIds`.
- Add the **Add/Edit Floor** page (`/admin/floors/new` and `/admin/floors/:id/edit`, built plainly — no design exists beyond the list): Floor Name, Building (dropdown, required), Capacity (a number plus a Guests/Staff unit), Access Level (Public/Restricted/Secure dropdown), Department(s) (multi-select checkboxes from the real department list), and Status toggle. Submitting resolves the floor's parent building, adds/updates/removes that floor within the building's `floors` array, and persists the whole building via `updateBuildingUseCase` — the exact mechanism `admin-buildings` already uses for its own nested floor edits, just entered from this page instead of the Building form.
- **Modifies `admin-buildings`**: its own Add/Edit Floor modal (used when adding or renaming a floor from within the Building form) gains the same new fields (Capacity, Access Level, Department(s), Status), so a floor's full detail is editable from either entry point and both stay in sync — there is exactly one stored floor record.
- Deleting a floor (from the Floors list) reuses the existing `ConfirmDialog`, resolves the parent building, removes the floor, and calls `updateBuildingUseCase`.
- Wires the `AdminSidebar`'s existing "Floors" nav item (key and label already exist, but `handleActivate` has no case for it) to navigate to `/admin/floors`.
- "Filters" is presented per the design but stays inert, matching the established pattern.

## Capabilities

### New Capabilities
- `admin-floors`: the global Floors Inventory page and the Add/Edit Floor page — listing every floor across every building, and adding, editing, and deleting a floor (as part of its parent building's data).

### Modified Capabilities
- `admin-buildings`: the Add/Edit Floor modal (reached from within the Building form) gains Capacity, Access Level, Department(s), and Status fields, matching the widened `Floor` entity.

## Impact

- **New routes**: `/admin/floors`, `/admin/floors/new`, `/admin/floors/:id/edit` in `src/App.tsx`.
- **Changed domain schema**: `src/domain/entities/building-schema.ts` — `FloorSchema` gains `capacityCount`, `capacityUnit`, `accessLevel`, `departmentIds`, `status`.
- **Changed presentation code**: `AdminSidebar.tsx` gains a `floors` case; `admin-buildings`'s `FloorModal.tsx` and `use-admin-building-form.ts` gain the new fields and load the department list.
- **New presentation code**: `src/presentation/pages/admin-floors/` (list page, form page, hooks, a `DepartmentMultiSelect` component).
- **No new data layer, infrastructure, or API endpoints** — `admin-floors` is built entirely on `listBuildingsUseCase`, `updateBuildingUseCase` (both from `admin-buildings`), and `listDepartmentsUseCase` (from `admin-departments`).
- **No backend changes are made by this change** — it assumes the existing `/buildings` endpoints accept and return the widened `Floor` shape.

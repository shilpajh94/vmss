## 1. Domain schema

- [x] 1.1 Widen `FloorSchema` in `src/domain/entities/building-schema.ts`: add `capacityCount` (number, default 0), `capacityUnit` (`'Guests' | 'Staff'`, default `'Guests'`), `accessLevel` (`'public' | 'restricted' | 'secure'`, default `'public'`), `departmentIds` (`string[]`, default `[]`), `status` (`'active' | 'inactive'`, default `'active'`)

## 2. Sidebar wiring

- [x] 2.1 Add a `floors` case to `AdminSidebar.tsx`'s `handleActivate` that navigates to `/admin/floors`

## 3. Shared: department multi-select

- [x] 3.1 Add `src/presentation/components/ui/DepartmentMultiSelect.tsx` (promoted to shared UI since it's used by both `admin-floors` and `admin-buildings`'s `FloorModal`, not page-local): a scrollable list of the existing `Checkbox` primitive, one per department, checked state driven by whether the department's id is in the current `departmentIds` array, calling back with the updated array on toggle

## 4. admin-buildings: extend the Floor modal

- [x] 4.1 In `use-admin-building-form.ts`, load the department list via `listDepartmentsUseCase` alongside branches; widen `saveFloor` to accept the full floor detail (capacity, access level, departmentIds, status) instead of only a name, applying sensible defaults when adding
- [x] 4.2 In `FloorModal.tsx` (admin-buildings), add Capacity (number `TextField` + Guests/Staff `SelectField`), Access Level `SelectField`, `DepartmentMultiSelect`, and a `ToggleSwitch` for status, alongside the existing Floor Name field; pre-fill all of them when editing

## 5. Floors list page

- [x] 5.1 Add `src/presentation/pages/admin-floors/hooks/use-admin-floors.ts`: auth-token gate; loads current staff user, every building (`listBuildingsUseCase`), and every department (`listDepartmentsUseCase`); derives the flat floor list (`buildings.flatMap(b => b.floors.map(f => ({ ...f, buildingId: b.id, buildingName: b.name })))`) and a department-name lookup; exposes loading/error/retry, `requestDelete`, `cancelDelete`, `confirmDelete` (resolves the floor's building, removes the floor from its `floors`, calls `updateBuildingUseCase`, updates local state, toasts)
- [x] 5.2 Add `src/presentation/pages/admin-floors/Components/FloorsTable.tsx`: table header (Floor Name/Number, Building, Department(s), Capacity, Access Level, Status, Actions); one row per floor with department names joined from the lookup, `{capacityCount} {capacityUnit}`, an Access Level badge (Public/Restricted/Secure, matching Figma's three colors), a Status badge (Active/Inactive), and Edit/Delete icon buttons (Edit navigates to `/admin/floors/:id/edit`)
- [x] 5.3 Add `src/presentation/pages/admin-floors/admin-floors.tsx`: renders `AdminSidebar` (`activeItem="floors"`), `AdminTopBar` (description mode), content header ("Floors Inventory" title, inert "Filters", "Add Floor" navigating to `/admin/floors/new`), `LoadingState`/inline-error-with-retry/`EmptyState`/`FloorsTable` depending on state, and a `ConfirmDialog` for delete

## 6. Add/Edit Floor page

- [x] 6.1 Add `src/presentation/pages/admin-floors/hooks/use-admin-floor-form.ts`: auth-token gate; loads every building and every department; reads an optional `:id` route param — when present, scans all buildings' floors for a matching id and pre-fills the form (including which building it currently belongs to) in edit mode, otherwise starts empty in add mode; exposes `updateField`, `submit` (validates name/building required; on save, resolves the target building — if editing and the building changed, removes the floor from the original building and adds it to the new one via two `updateBuildingUseCase` calls, otherwise one call updating the floor in place; on success navigates to `/admin/floors` and toasts success; on failure toasts error and keeps entered values), and `cancel` (navigates to `/admin/floors`)
- [x] 6.2 Add `src/presentation/pages/admin-floors/admin-floor-form.tsx`: renders `AdminSidebar` (`activeItem="floors"`), `AdminTopBar` (description mode), a back button + "Add Floor"/"Edit Floor" header, a form card (Floor Name `TextField`, Building `SelectField`, Capacity `TextField` + unit `SelectField`, Access Level `SelectField`, `DepartmentMultiSelect`, Status `ToggleSwitch`), and Cancel/Save Floor footer actions

## 7. Routing

- [x] 7.1 Add `/admin/floors`, `/admin/floors/new`, and `/admin/floors/:id/edit` routes to `src/App.tsx`

## 8. Verification

- [x] 8.1 Run the dev server and visually compare `/admin/floors` against the Figma design (node `203:647`) for layout, spacing, badge colors, and column fidelity
- [x] 8.2 Manually verify: Floors nav item navigates, list load/error/retry, empty state, Add Floor navigation + validation + success + failure, Building/Department options populated from real data, Edit pre-fills every field and updates, moving a floor to a different building on edit, Delete confirm/cancel/success/failure, inert Filters
- [x] 8.3 Manually verify: adding/editing a floor from within the Building form (admin-buildings) now captures and pre-fills capacity/access level/departments/status, and that a floor added there appears correctly on `/admin/floors`
- [x] 8.4 Run lint/type-check and any existing test suite

## 1. Fetch and populate the building's own details on edit

- [x] 1.1 In `src/presentation/pages/admin-buildings/hooks/use-admin-building-form.ts`, add `listBuildingsUseCase.execute()` to the edit-mode branch of `load()` (alongside the existing `listFloorsUseCase.execute(id)` call), find the building matching `id`, and call `setDetails(...)` with its `name`, `branchId`, `code`, `address`, and `isActive`.
- [x] 1.2 If no building matches `id`, set `errorMessage` (e.g. "That building could not be found.") and call `toast.error(...)`, following the same pattern as `use-admin-department-form.ts`'s edit-mode load, instead of leaving the form on `EMPTY_DETAILS`.
- [x] 1.3 Keep the existing floors fetch and behavior unchanged.

## 2. Verify

- [ ] 2.1 From `/admin/buildings`, activate "Edit" on an existing building and confirm the Building Name, Branch, Code, Address, and Status fields are pre-filled with that building's current values (not blank/default).
- [ ] 2.2 Submit the edit form without changing anything and confirm the update succeeds and the table still shows the same (unchanged) values afterward — i.e. saving no longer risks overwriting real values with defaults.
- [ ] 2.3 Navigate directly to `/admin/buildings/:id/edit` with an id that doesn't exist and confirm an error message shows instead of a blank form.

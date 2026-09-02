## Why

When an admin opens the Edit Building page, the form's building-details fields (name, branch, code, address, status) render empty instead of pre-filled with the building's current values — even though the spec already requires the page to open "pre-filled with that building's current details." Only the building's floors currently load; the building's own details never do, so every edit starts from a blank/default form and any save risks silently overwriting real values with defaults.

## What Changes

- Fix `useAdminBuildingForm`'s edit-mode load so it fetches the building being edited and populates the form's details (name, branch, code, address, status) from it, in addition to the floors it already loads.
- No visible new UI — this restores already-specified behavior that isn't currently implemented correctly.

## Capabilities

### New Capabilities
(none)

### Modified Capabilities
- `admin-buildings`: clarify the existing "Editing a building opens the same page pre-filled with its current details" requirement to make explicit that the building's own details (not just its floors and checkpoints) must be fetched and populated, since the current implementation only fetches floors.

## Impact

- `src/presentation/pages/admin-buildings/hooks/use-admin-building-form.ts` — `load()`'s edit-mode branch needs to also resolve the building being edited (by `id`) and call `setDetails(...)` with its `name`, `branchId`, `code`, `address`, `isActive`.
- No new endpoint required: `listBuildingsUseCase` returns the full building list; the same list+find-by-id pattern already used in `use-admin-department-form.ts`'s edit-mode load applies here. See design.md.

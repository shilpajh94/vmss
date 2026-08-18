## Context

See `proposal.md` - Why. This is the fifth Admin-section page, and the first to be built entirely on top of an existing capability's data rather than its own endpoints:

- `Floor` (`src/domain/entities/building-schema.ts`) currently lives only nested inside `Building.floors`, with shape `{ id, name, checkpoints }`. `admin-buildings` already owns the only mechanism that persists a floor: `updateBuildingUseCase.execute(id, buildingInputWithFloors)`.
- `admin-departments` exposes `listDepartmentsUseCase`; `admin-buildings` exposes `listBuildingsUseCase`/`updateBuildingUseCase`. This change is the first to consume use cases from two other capabilities in one page.
- The user confirmed: extend `Floor` in place (capacity, access level, department links, status) rather than inventing a parallel entity, and ship full CRUD via a plain (undesigned) Add/Edit Floor page.
- `AdminSidebar` already declares `'floors'` and renders the nav item; `handleActivate` has no case for it yet — the same gap already fixed for `branches`/`departments`/`buildings`.
- No shared multi-select component exists. The existing `Checkbox` primitive (`src/presentation/components/ui/Checkbox.tsx`) already renders a single labeled checkbox; a department multi-select is a page-local list of these, not a new shared primitive.

## Goals / Non-Goals

**Goals:**
- Match the Floors Inventory list (node `203:647`) pixel-for-pixel, including the three-tier Access Level badge (Public/Restricted/Secure) and per-floor Status badge.
- Keep exactly one stored representation of a floor — extending it, and updating both entry points (this page, and `admin-buildings`'s floor modal) to read/write the same fields.
- Reuse `listBuildingsUseCase`, `updateBuildingUseCase`, and `listDepartmentsUseCase` as-is; add no new endpoints, repositories, or use cases.

**Non-Goals:**
- No new backend resource for "floor" — it is still persisted exclusively as part of its parent building's `floors` array.
- No bidirectional link on `Department` (no `floorId`/`buildingId` added there) — the association is one-directional, `Floor.departmentIds` referencing `Department.id`, so `admin-departments`'s schema and requirements are untouched.
- No Security Checkpoints changes — checkpoints keep working exactly as `admin-buildings` already built them; this change only adds sibling fields to `Floor`, none of which touch `checkpoints`.

## Decisions

- **`Floor` gains `capacityCount: number`, `capacityUnit: 'Guests' | 'Staff'`, `accessLevel: 'public' | 'restricted' | 'secure'`, `departmentIds: string[]`, `status: 'active' | 'inactive'`.** All five default sensibly (`capacityCount: 0`, `capacityUnit: 'Guests'`, `accessLevel: 'public'`, `departmentIds: []`, `status: 'active'`) so floors created before this change — or via `admin-buildings`'s existing simple flow before its modal is updated — still validate against the widened schema.
- **The Floors list is computed, not fetched from a dedicated endpoint.** `useAdminFloors` calls `listBuildingsUseCase.execute()` and `listDepartmentsUseCase.execute()`, then flattens `buildings.flatMap(b => b.floors.map(f => ({ ...f, buildingId: b.id, buildingName: b.name })))`. Department names for display are resolved by looking up each floor's `departmentIds` against the loaded department list at render time — no denormalized `departmentNames` field is added to the schema, avoiding a second source of truth for something already fully derivable.
- **Floor CRUD from `/admin/floors` reuses `updateBuildingUseCase` exclusively, never a "create/delete floor" use case.** Add: load the target building, append a new floor (`crypto.randomUUID()` id, matching `admin-buildings`'s existing pattern) to its `floors`, call `updateBuildingUseCase.execute(buildingId, {...buildingInput, floors: nextFloors})`. Edit/Delete: same shape, replacing or filtering the matching floor by id. This is the same mechanism `admin-buildings` already uses for its own nested floor edits — just entered from a different page.
- **Floor lookup by id alone, not `(buildingId, floorId)`.** Floor ids are already client-generated UUIDs (or backend-assigned unique ids) with no reuse across buildings, so `/admin/floors/:id/edit` can resolve both the floor and its parent building by scanning all buildings' `floors` for a matching id — no need to thread a building id through the URL.
- **Editing a floor's building (moving it between buildings) is supported by the same mechanism**: on submit, if the selected building differs from the floor's original building, the use case removes the floor from the original building's `floors` and adds it to the newly selected building's `floors` — two `updateBuildingUseCase` calls in that case, one otherwise. This isn't shown in the Figma list, but the Add/Edit form necessarily offers a Building field, so a change to it needs defined behavior rather than being silently ignored.
- **Department multi-select is a page-local `DepartmentMultiSelect` component**, a scrollable list of the existing `Checkbox` primitive (one per department), not a new shared dropdown-with-checkboxes widget — there's no design to match beyond "Department(s)" being a comma-separated list in the table, so the simplest input that produces that list is enough.
- **`admin-buildings`'s `FloorModal` is extended in place** with the same Capacity/Access Level/Department(s)/Status fields (reusing the new `DepartmentMultiSelect`), so a floor's full detail is reachable and consistent whether entered from the Building form or from `/admin/floors`.
- **Access Level and Status badges use arbitrary Tailwind colors matching Figma exactly** (`bg-[#dbeafe] text-[#1e40af]` Public, `bg-[#fef3c7] text-[#92400e]` Restricted, `bg-[#fee2e2] text-[#991b1b]` Secure) since no existing theme token pair matches this three-tier scheme; the existing `success`/`border-subtle` token pair is reused for the Active/Inactive status badge, consistent with every other list page in this Admin section.

## Risks / Trade-offs

- [Floors list computed by loading every building] → Fine at the scale implied by the Figma mock (a handful of buildings/floors); if the organisation grows large, a dedicated paginated list-floors endpoint would be a better fit — not needed today.
- [Moving a floor between buildings costs two `updateBuildingUseCase` calls] → Slightly more complex than a single call, and not atomic (a failure between the two calls could leave the floor in neither or both buildings); acceptable for an admin tool at this scale, revisit if this becomes a real backend resource with its own endpoint.
- [`Floor.departmentIds` has no reverse link on `Department`] → An admin viewing a department has no way to see which floors reference it without visiting `/admin/floors`; acceptable since `admin-departments` doesn't currently show any floor/building info either.

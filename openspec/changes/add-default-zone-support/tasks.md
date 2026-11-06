## 1. Data layer

- [x] 1.1 Add `isDefault: z.boolean().default(false)` to `ZoneSchema` and `isDefault?: boolean` to `ZoneInput` in `src/domain/entities/zone-schema.ts`
- [x] 1.2 Add `isDefault?: boolean` to `ListZonesParams` in `src/data/repositories/zone-repository.ts`
- [x] 1.3 Forward `isDefault` as a query param in `HttpZoneRepository.list` (`src/infrastructure/zone-repository.ts`)

## 2. Zones admin

- [x] 2.1 Add a "Default zone" `ToggleSwitch` with helper text to `admin-zone-form.tsx`; include `isDefault` in `use-admin-zone-form.ts` state, load and payload; disable it while the zone is inactive
- [x] 2.2 Block deactivating a zone whose default toggle is on, with "Choose another default zone first."
- [x] 2.3 Add a shared helper mapping 409 to "Choose another default zone first."; use it in `use-admin-zone-form.ts` submit and `use-admin-zones.ts` `confirmDelete`
- [x] 2.4 Show a "Default" badge beside the zone name in `ZonesTable.tsx`
- [x] 2.5 Add a "Default zone" filter (All / Default / Not default) to `use-admin-zones.ts` and the filter panel in `admin-zones.tsx`; include it in `isFiltering` and `clearFilters`

## 3. Visit zone picker

- [x] 3.1 In `use-zone-set.ts`, derive `defaultZone` (active, `isDefault`) for invitation scope only; keep it out of `draft`, `savedIds` and `isDirty`; make `deniesEverything` false when a default exists
- [x] 3.2 In `ZonePicker.tsx`, render the default zone as a locked "Always allowed" chip in edit and readonly modes, excluded from the checkbox list
- [x] 3.3 In `ZoneSetSection.tsx`, show the neutral "only the default zone is allowed" notice instead of the denied warning when appropriate

## 4. Verification

- [x] 4.1 Run `tsc` (no ESLint config in repo); confirm a zone response without `isDefault` still parses
- [ ] 4.2 Manually check: set/move/clear default, 409 on delete and deactivate, filter, chip in visit picker, and that the PUT body omits the default zone
- [ ] 4.3 Merge only after the backend is deployed (unknown-field risk noted in design.md)

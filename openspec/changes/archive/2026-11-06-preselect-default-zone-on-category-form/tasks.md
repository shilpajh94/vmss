## 1. Create-mode zone state

- [x] 1.1 In `use-admin-visitor-category-form.ts`, for create mode with the zone feature enabled and `zones:manage`, load active zones (`fetchAllPages` over `listZonesUseCase`) and the default (`listZonesUseCase.execute({ isDefault: true, isActive: true, pageSize: 1 })`); expose `zones`, `zoneDraft`, `toggleZone`, and a loading/error phase
- [x] 1.2 Seed `zoneDraft` once from the default zone's id (or `[]` when none); never reseed after the admin edits it
- [x] 1.3 Treat a 404 as "feature off" via `reportDisabled()`; any other default-lookup failure leaves the checklist unticked and does not block the form

## 2. Save flow

- [x] 2.1 After `createVisitorCategoryUseCase.execute`, call `setCategoryZonesUseCase.execute(created.id, zoneDraft)` when `zoneDraft.length > 0` and the user can manage zones; skip otherwise
- [x] 2.2 Wrap the call in its own try/catch: on failure keep the category, show "Category created, but zones could not be saved. Set them from the Edit page.", and navigate to that category's Edit page (verify the route path)
- [x] 2.3 Keep the existing success toast, Reception-workflow step and `release()`/navigation behaviour on the happy path

## 3. UI

- [x] 3.1 Add a presentational `ZoneDraftSection` (title "Default zones", help text, loading and error states) around `ZonePicker` in `src/presentation/components/zones/`
- [x] 3.2 Render it in `admin-visitor-category-form.tsx` for create mode only, gated on `useZoneFeature().enabled` and `canManageZones`; leave the edit-mode `ZoneSetSection` untouched

## 4. Verification

- [x] 4.1 `npm run build` / lint / type-check pass
- [ ] 4.2 Manually check: default pre-checked and untickable; no default → nothing checked; feature off → no checklist; zones PUT failure → category kept and Edit page shown; Edit page does not pre-select the default

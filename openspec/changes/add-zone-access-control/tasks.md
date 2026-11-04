## 1. Contracts and data layer

- [x] 1.1 Add zone endpoints (list, create, get, update, delete, category get/set, invitation get/set, emergency inside) to `API_ENDPOINTS`, all `hasToken: true`
- [x] 1.2 Add `zone-schema.ts` and `emergency-inside-schema.ts` under `src/domain/entities/` with `z.infer` types and the paginated list envelope
- [x] 1.3 Add `ZoneRepository` and `EmergencyInsideRepository` ports under `src/data/repositories/`
- [x] 1.4 Implement both adapters under `src/infrastructure/` (zone list passes `X-Branch-ID` when a branch is selected; update body omits `branchId`)
- [x] 1.5 Add use cases under `src/data/use-cases/` and wire lazy resolvers plus `AppDependencies` entries in `src/composition-root.ts`
- [x] 1.6 Add unit tests for schema parsing (zone, mapping, inside report incl. empty `unzoned`) in `tests/unit/`

## 2. Permissions and feature gate

- [x] 2.1 Add `zones`, `zonesManage` and `emergencyInside` to `PAGE_PERMISSIONS`; add `zones:manage` to `ADMIN_AREA_PERMISSIONS`
- [x] 2.2 Add the proposed grants to the fallback role table (`zones:manage`: admin; `zones:view` and `emergency:view`: admin, reception, security)
- [x] 2.3 Add a zone-feature hook/provider that calls `GET /zones` once and sets `enabled=false` only on a 404 (403 is not "off"); skip the call without `zones:view`
- [x] 2.4 Unit test the gate: 404 → hidden, 403 → hidden without disabling, success → enabled

## 3. Zone admin screen

- [x] 3.1 Add `/admin/zones` list page with active filter, name/created-date sort, paging, empty state, error and retry
- [x] 3.2 Add Add/Edit Zone page: required branch, name, code; building → floor → gates cascading choices; branch read-only on edit; active toggle on edit
- [x] 3.3 Add delete with confirmation and success/error notifications
- [x] 3.4 Show Add/Edit/Delete only with `zones:manage`; add the Zones sidebar item gated by `zones:view` and the feature gate
- [x] 3.5 Register the routes in `App.tsx` with `requires` permissions and the auth redirect

## 4. Zone picker and visit/category integration

- [x] 4.1 Build the shared `ZonePicker` (zones of one branch, inactive disabled, edit/read-only modes, defaults-apply and denied-everywhere states)
- [x] 4.2 Add the default-zones section to the Edit Category page (view with `zones:view`, save with `zones:manage`, empty-defaults warning, hidden on Add and when the feature is off)
- [x] 4.3 Add the zone section to the visit detail view: load the visit's zones, fall back to the category defaults for display, whole-set PUT gated by `invitations:edit`, 422 shown inline, clear = category defaults
- [x] 4.4 Add the post-registration "Set zones" step to the staff registration success state; call the PUT only after the visit exists and keep the visit on failure with a retry path
- [x] 4.5 Add the new timeline event types, labels, and icons (denial uses the warning token) to `visit-timeline-schema.ts` and `VisitTimeline.tsx`

## 5. Inside-by-zone view

- [x] 5.1 Add the `/emergency/inside` page grouped by zone with a "Not in a zone" group, total inside, empty state, error and retry
- [x] 5.2 Add manual refresh with last-loaded time; gate the page and its nav entry by `emergency:view` and the feature gate
- [x] 5.3 Confirm the full list renders with no truncation for a large fixture

## 6. Verification

- [x] 6.1 Run `npm run lint`, `npm test`, and `npm run build`
- [ ] 6.2 Exercise each flow in the dev server with the backend flag on, and confirm all zone UI is absent with it off
- [ ] 6.3 Check light/dark themes and mobile width for the new pages and the picker

## 7. Tenant switch

- [x] 7.1 Read and write `zoneAccessEnabled` through the tenant settings repository and use cases
- [x] 7.2 Add the Zone Access Control card to Organisation Configs (hidden without `tenants:update`) and re-probe the feature gate after a save

## 1. Data layer

- [x] 1.1 Add Zod schemas under `src/domain/entities/` for device (list item, paged list, update response) and the kiosk location validation setting
- [x] 1.2 Add `LIST_DEVICES`, `APPROVE_DEVICE`, `ENABLE_DEVICE`, `DISABLE_DEVICE`, `DELETE_DEVICE`, `GET/UPDATE_KIOSK_LOCATION_VALIDATION` to `API_ENDPOINTS` (hasToken true)
- [x] 1.3 Add `DeviceRepository` and setting repository ports in `src/data/repositories/`
- [x] 1.4 Implement adapters in `src/infrastructure/` using `ApiClient.makeRequest` (handle 204 delete)
- [x] 1.5 Add use cases (list, approve, enable, disable, delete, get/update setting) and wire in `composition-root.ts` + `AppDependencies`

## 2. Permissions

- [x] 2.1 Ensure `devices:view|manage|approve` and `settings:view|manage` render and are assignable in the role permission UI
- [x] 2.2 Add a permission-check helper/source for gating pages, actions, and the setting

## 3. Device list pages

- [x] 3.1 Build the shared `use-admin-devices(operatingMode)` hook: paging, sort, branch/building/status filters, status→query mapping, row actions, 409 and 403 handling
- [x] 3.2 Build the shared `DevicesTable` and filter panel with `canApprove/canEnable/canDisable`-driven buttons and delete confirmation
- [x] 3.3 Rewire Reception Desks (`kiosk`) and Security Gates (`security`) pages to the shared hook/table
- [x] 3.4 Remove legacy desk/gate forms, hooks, use cases, repositories, endpoints, and composition entries; redirect legacy `/new` and `/:id/edit` routes to the lists
- [x] 3.5 Update top-bar descriptions and empty/error states for devices

## 4. Kiosk location validation setting

- [x] 4.1 Add the toggle card to the admin settings host (Organisation Configs) with view-only vs manage behavior and revert-on-failure

## 5. Invitation detail

- [x] 5.1 Extend invitation-detail schema with nullable `checkInDevice`/`checkOutDevice`
- [x] 5.2 Show device info in `VisitorInfoModal` next to check-in/out times

## 6. Verification

- [ ] 6.1 Unit-test the status→query mapping and permission gating (blocked: repo has no test runner configured)
- [x] 6.2 Run typecheck, lint, and build
- [ ] 6.3 Manually verify both pages against the stage API: filters, approve/enable/disable/delete, 409/403 paths, setting toggle

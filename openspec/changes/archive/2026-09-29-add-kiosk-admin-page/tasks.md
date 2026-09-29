## 1. Data layer

- [x] 1.1 Add `LIST_KIOSKS`, `GET_KIOSK`, `CREATE_KIOSK`, `UPDATE_KIOSK`, `SET_KIOSK_VISIBILITY`, `DELETE_KIOSK` to `src/data/api/api-endpoints.ts` (all `hasToken: true`); confirm no `X-Branch-ID` is sent for them
- [x] 1.2 Create `src/domain/entities/kiosk-schema.ts` with `KioskSchema`/`Kiosk`, `KioskInput`, single and list (with `pagination`) response envelope schemas
- [x] 1.3 Create `KioskRepository` port in `src/data/repositories/kiosk-repository.ts` (`listPage`, `get`, `create`, `update`, `setHidden`, `remove`)
- [x] 1.4 Create `HttpKioskRepository` in `src/infrastructure/kiosk-repository.ts` using `makeRequest` with `pathParams`/`queryParams` (`status`, `includeHidden`, `sortBy`, `sortOrder`)
- [x] 1.5 Create use cases in `src/data/use-cases/`: list-kiosks-page, get-kiosk, create-kiosk, update-kiosk, set-kiosk-visibility, delete-kiosk
- [x] 1.6 Wire `ApiClient → HttpKioskRepository → use cases` lazily in `src/composition-root.ts` and add them to `AppDependencies`

## 2. Kiosks list page

- [x] 2.1 Create `src/presentation/pages/admin-kiosks/hooks/use-admin-kiosks.ts` (paging, status filter, show-hidden, sort, polling, delete/hide/toggle-active actions, `canManage`, error mapping)
- [x] 2.2 Create `Components/KiosksTable.tsx` with Name, Description, Active toggle, "Hidden" badge, and Edit / Hide-Unhide / Delete actions shown only when `canManage`
- [x] 2.3 Create `admin-kiosks.tsx` page with filters, sort control, "Show hidden" toggle, empty/loading/error states, paging, Add button (manage only), and delete `ConfirmDialog` (irreversible warning)

## 3. Add/Edit form

- [x] 3.1 Create `hooks/use-admin-kiosk-form.ts`: load via get-kiosk in edit mode, validate name (1–255, trimmed) and description (≤ 2000), map 409 to the name field, 404 to navigate back with notice, 422 to a toast
- [x] 3.2 Create `admin-kiosk-form.tsx` (name, description, Active toggle; `preventDefault` on submit; Cancel returns to list)

## 4. Navigation and gating

- [x] 4.1 Add routes `/admin/kiosks`, `/admin/kiosks/new`, `/admin/kiosks/:id/edit` in `src/App.tsx`; redirect non-managers away from new/edit
- [x] 4.2 Add "Kiosks" item, path mapping, and navigate handler to `src/presentation/components/AdminSidebar.tsx`
- [x] 4.3 Add a single `canManageKiosks(user)` helper (currently `user.isAdmin`) used by list and form

## 5. Verification

- [x] 5.1 Run `tsc`/lint and build; fix type errors
- [ ] 5.2 Manually verify against the API: list defaults, status filter, sort, show-hidden + badge, create, edit (incl. hidden kiosk), hide/unhide leaves Active unchanged, delete confirm/cancel, 409 on name field, view-only hides write actions

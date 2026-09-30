## Context

Admin registers (security gates, departments, reception desks) already follow a fixed shape: `API_ENDPOINTS` entries → Zod schemas in `domain/entities` → port in `data/repositories` → adapter in `infrastructure` → use cases in `data/use-cases` → wiring in `composition-root.ts` → page + hooks under `presentation/pages/admin-*`. Security Gates is the closest analog (paginated list via `usePagedList`, `usePolling`, `ConfirmDialog`, separate form page). See proposal.md for motivation.

Differences from those pages: kiosks are company-wide (no branch/building joins, no name lookups), the API has server-side `status`, `includeHidden`, `sortBy`/`sortOrder` params, a dedicated visibility endpoint, and returns 409 for duplicate names. Also, `/auth/me` (`UserOutSchema`) exposes only `branchRoles`, not permission codes, and `StaffUser` carries just `isAdmin`/`isReception`.

## Goals / Non-Goals

**Goals:**
- Full kiosk register matching the API guide, following existing layering and Tailwind/UI components.
- Keep Active and Hidden as independent controls.

**Non-Goals:**
- Fetching effective permission codes from the backend or changing the roles UI.
- Kiosk device pairing, kiosk-side UI, or branch-scoped kiosks.
- Bulk actions.

## Decisions

1. **Endpoints**: add `LIST_KIOSKS` (GET `/kiosks`), `GET_KIOSK` (GET `/kiosks/:id`), `CREATE_KIOSK`, `UPDATE_KIOSK` (PUT), `SET_KIOSK_VISIBILITY` (PATCH `/kiosks/:id/visibility`), `DELETE_KIOSK`; all `hasToken: true`. `pathParams` is already supported by `ApiClient`, and 204 handling exists. No `X-Branch-ID` is added; verify `ApiClient` doesn't inject one globally for these routes, and if it does, add an opt-out.

2. **Schemas**: `kiosk-schema.ts` holds `KioskSchema` (`id, name, description (nullable→optional), isActive, isHidden`) and `Kiosk` type, plus a `KioskInput` (`name, description?, isActive`). Response envelope schemas (single + list with `pagination`) follow the `*-out-schema.ts` convention. Since the API already returns the domain shape there is no name-lookup mapping, so a single schema file with envelopes is enough; the adapter just unwraps `data`.

3. **Port** `KioskRepository`: `listPage({page, pageSize, status?, includeHidden, sortBy, sortOrder}) → {items, total}`, `get(id)`, `create(input)`, `update(id, input)`, `setHidden(id, isHidden)`, `remove(id)`. Use cases: `ListKiosksPageUseCase`, `GetKioskUseCase`, `CreateKioskUseCase`, `UpdateKioskUseCase`, `SetKioskVisibilityUseCase`, `DeleteKioskUseCase`. `includeHidden` is sent explicitly (`false` by default).

4. **Toggle Active from the list** reuses `UpdateKioskUseCase` with only `{isActive}` (PUT accepts any subset), so no extra endpoint. The update input type is therefore `Partial<KioskInput>`.

5. **Permission gating (interim)**: because permission codes aren't available client-side, `canManage` is derived from `StaffUser.isAdmin` (guide states Admin has both permissions), and the Add/Edit routes redirect non-managers to the list. The server remains authoritative: 403 is already turned into an `ApiError` with a permission message by `ApiClient`. A view-only non-admin role would therefore currently see no write actions even if granted `kiosks:manage`. Rejected alternative: extending `/auth/me` parsing to read a `permissions` array that may not exist; deferred until the backend confirms the field (recorded in Open Questions). Isolating the check in one `canManageKiosks(user)` helper keeps the later switch to permission codes to a single place.

6. **Error mapping**: `ApiError` carries `status`. Hooks branch on it: 409 → `errors.name` on the form; 404 → toast + list refresh (form: navigate to list); 422 → toast with the server message (`ApiError.message` already extracts it), form values preserved; 401 handled by `ApiClient`/existing redirect pattern.

7. **List state**: filters (`status`, `showHidden`, `sortBy`, `sortOrder`) live in `use-admin-kiosks.ts`, each setter calls `resetToFirstPage()`, mirroring `use-admin-security-gates.ts`. Polling (15 s, paused while a dialog/mutation is open) and `usePageRefresh` are kept for consistency. Hide/unhide and active-toggle refresh the list silently after success.

8. **Form**: reuse `TextField`, `TextareaField`, `ToggleSwitch`; client validation mirrors the server (name trimmed 1–255, description ≤ 2000); `e.preventDefault()` on submit. Edit mode loads via `GetKioskUseCase` (works for hidden kiosks) rather than scanning the list, avoiding the pagination/hidden pitfall the departments form has.

9. **Delete**: `ConfirmDialog` stating the action cannot be undone, as in security gates.

## Risks / Trade-offs

- [Admin-only gating hides write actions from non-admin roles with `kiosks:manage`] → single helper + Open Question; server still enforces.
- [Hiding a kiosk while "Show hidden" is off removes the row immediately, which may surprise] → success toast says "Kiosk hidden".
- [Polling refresh could reset a row's optimistic state] → pause polling while a mutation is in flight.
- [API guide text was truncated in places] → assumptions below; confirm against the backend before merging.

## Assumptions

- Truncated "Show hidden" note: toggle sends `includeHidden=true`.
- Truncated 409 note: names are unique case-insensitively among non-deleted kiosks and a deleted kiosk's name can be reused; the UI just shows the server's 409 on the name field.
- Truncated PUT note: `isHidden` is changed only via the visibility endpoint (already stated by the guide).
- Sort UI offers Name and Created date with asc/desc; default name asc.

## Open Questions

- Will `/auth/me` expose permission codes (`kiosks:view`/`kiosks:manage`) so gating can move off `isAdmin`? Does not change specs or task breakdown beyond one helper.

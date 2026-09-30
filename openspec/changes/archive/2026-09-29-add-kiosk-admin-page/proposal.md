## Why

Admins have no way to manage kiosks in the admin console, although the backend now exposes a company-wide `/kiosks` API (list, get, create, edit, hide/unhide, delete). Kiosks are the physical check-in devices; without a register screen they can only be managed through the API directly.

## What Changes

- Add an admin **Kiosks** register at `/admin/kiosks`, modelled on the existing Security Gates / Departments pages: paginated table, status filter, sortable columns, "Show hidden" toggle, "Hidden" badge on hidden rows.
- Add Add / Edit form pages at `/admin/kiosks/new` and `/admin/kiosks/:id/edit` (name required 1–255 chars, description optional ≤ 2000 chars, Active toggle).
- Add a **Hide / Unhide** row action (`PATCH /kiosks/{id}/visibility`), kept separate from the Active toggle, since hiding does not deactivate a kiosk.
- Add **Delete** with a confirm dialog (irreversible).
- Show Add / Edit / Hide / Delete only to users with manage rights; view-only users see the list without write actions.
- Surface API errors: 401 → redirect to login, 403 → permission message, 404 → refresh list, 409 → inline error on the name field, 422 → validation message.
- Add a "Kiosks" entry to the admin sidebar and routes in `App.tsx`.
- No X-Branch-ID header; kiosks are company-wide.

## Capabilities

### New Capabilities
- `admin-kiosks`: Admin Kiosks register and Add/Edit form — list with filter/sort/pagination and hidden-kiosk handling, create, edit, hide/unhide, delete with confirmation, permission-gated write actions, and API error mapping.

### Modified Capabilities

## Impact

- New: kiosk endpoints in `src/data/api/api-endpoints.ts`, `src/domain/entities/kiosk-schema.ts` (+ response schemas), `src/data/repositories/kiosk-repository.ts` (port), `src/infrastructure/kiosk-repository.ts` (adapter), kiosk use cases under `src/data/use-cases/`, and `src/presentation/pages/admin-kiosks/`.
- Modified: `src/composition-root.ts` (wiring + `AppDependencies`), `src/App.tsx` (routes), `src/presentation/components/AdminSidebar.tsx` (nav item).
- Permissions: `/auth/me` does not currently expose permission codes (`kiosks:view` / `kiosks:manage`); see design for the interim gating decision.
- Backend dependency: `/api/v1/kiosks` endpoints as described in the API guide; the guide's text was truncated in places (see design "Assumptions").

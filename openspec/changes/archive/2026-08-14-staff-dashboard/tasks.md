## 1. Domain schemas

- [x] 1.1 Add `VisitRequestSummarySchema` (`id`, `reqId`, `visitorName`, `visitorInitials`, `hostName`, `scheduledAt`, `status`) and its `z.infer` type under `src/domain/entities/visit-request-summary-schema.ts`, with `status` as `z.enum(["requested", "approved", "checked_in", "denied"])`
- [x] 1.2 Add `StaffUserSchema` (`name`, `role`) and its `z.infer` type under `src/domain/entities/staff-user-schema.ts`

## 2. API endpoints

- [x] 2.1 Add `LIST_VISIT_REQUESTS` (`GET`, `hasToken: true`) to `src/data/api/api-endpoints.ts`
- [x] 2.2 Add `GET_CURRENT_STAFF_USER` (`GET`, `hasToken: true`) to `src/data/api/api-endpoints.ts`

## 3. Ports

- [x] 3.1 Add `VisitRequestSummaryRepository` interface (`list(): Promise<VisitRequestSummary[]>`) under `src/data/repositories/visit-request-summary-repository.ts`
- [x] 3.2 Add `getCurrentUser(): Promise<StaffUser>` to `StaffAuthRepository` in `src/data/repositories/staff-auth-repository.ts`

## 4. Adapters

- [x] 4.1 Add `HttpVisitRequestSummaryRepository` under `src/infrastructure/visit-request-summary-repository.ts`, implementing `list()` via `apiClient.makeRequest` with `API_ENDPOINTS.LIST_VISIT_REQUESTS` and `VisitRequestSummarySchema` (array)
- [x] 4.2 Implement `getCurrentUser()` on `HttpStaffAuthRepository` in `src/infrastructure/staff-auth-repository.ts` via `apiClient.makeRequest` with `API_ENDPOINTS.GET_CURRENT_STAFF_USER` and `StaffUserSchema`

## 5. Use cases

- [x] 5.1 Add `ListVisitRequestsUseCase` under `src/data/use-cases/list-visit-requests.ts`, constructor-injected with `VisitRequestSummaryRepository`
- [x] 5.2 Add `GetCurrentStaffUserUseCase` under `src/data/use-cases/get-current-staff-user.ts`, constructor-injected with `StaffAuthRepository`

## 6. Composition root

- [x] 6.1 Add lazy resolvers for `VisitRequestSummaryRepository`, `ListVisitRequestsUseCase`, and `GetCurrentStaffUserUseCase` in `src/composition-root.ts`
- [x] 6.2 Expose `listVisitRequestsUseCase` and `getCurrentStaffUserUseCase` on `AppDependencies`

## 7. Presentation - hook

- [x] 7.1 Create `src/presentation/pages/staff-dashboard/hooks/use-staff-dashboard.ts`: on mount, check `sessionStorage.getItem('token')` and redirect to `/staff/login` (via `react-router`'s `navigate`, `replace: true`) if absent
- [x] 7.2 In the hook, load the current staff user and the visit-requests list via `useAppDependencies()`, expose loading/error/data state
- [x] 7.3 Add a `refresh()` action that re-runs the visit-requests fetch
- [x] 7.4 Add a `signOut()` action that clears the token from `sessionStorage` and navigates to `/staff/login`
- [x] 7.5 Add `search` state and a derived, case-insensitive filtered list (matches visitor name, host name, or REQ ID)
- [x] 7.6 Derive the four status-column groupings (Requested, Approved, Checked-in, Denied) with counts from the filtered list

## 8. Presentation - components

- [x] 8.1 Add `Components/DashboardSidebar.tsx` (brand mark, "All visitors" / "My actions" / "Audit trail" nav with "All visitors" marked active, "Help & Support" link — the latter three inert)
- [x] 8.2 Add `Components/WorkspaceHeader.tsx` ("Visits" title/subtitle, current user name/role, refresh action, sign-out action)
- [x] 8.3 Add `Components/SearchActionBar.tsx` (search input wired to hook state, inert "Filters" button)
- [x] 8.4 Add `Components/VisitRequestCard.tsx` (avatar initials, REQ ID, visitor name, host name, scheduled date/time)
- [x] 8.5 Add `Components/KanbanColumn.tsx` (column header with title + count badge, renders cards or an empty-state message)
- [x] 8.6 Add icons needed for these components as inline `currentColor` SVG components under `Components/icons.tsx`, colocated with the dashboard rather than `src/assets/icons.ts` — the global barrel's `<img src>` pattern bakes a fixed color into each asset and can't support the sidebar/header icons' state-dependent coloring; this mirrors the existing `staff-login` screens' inline-SVG convention

## 9. Presentation - page

- [x] 9.1 Rewrite `src/presentation/pages/staff-dashboard/staff-dashboard.tsx` to compose the sidebar, workspace header, search bar, and the four kanban columns using `use-staff-dashboard.ts` and the new components
- [x] 9.2 Render a load-error state with a retry action when the visit-requests fetch fails
- [x] 9.3 Style per the Figma design (VMS file, node 31:4) using Tailwind v4 and existing `--color-*` theme tokens

## 10. Verification

- [x] 10.1 Run the dev server and manually verify: redirect when no token, dashboard render with token, search filtering, refresh, sign-out, and the empty-state column
- [x] 10.2 Run typecheck/lint/build and fix any errors

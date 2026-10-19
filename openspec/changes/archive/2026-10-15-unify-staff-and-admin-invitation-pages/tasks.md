## 1. Shared top bar

- [x] 1.1 Generalize `src/presentation/components/AdminTopBar.tsx` into a shared `AppTopBar` with these props: `title`, `description`, `breadcrumb`, `currentUser`, `navLabelFor`, `loginPath`. It keeps `RefreshControl`. `AdminLayout` passes the admin values, and admin pages must render exactly as before.
- [x] 1.2 Add `staffNavLabelFor(pathname)`: `/staff/dashboard` → "Invitations", `/staff/visitors/new` → "My actions".
- [x] 1.3 `src/presentation/components/StaffLayout.tsx`:
  - Wrap the content in `PageHeaderProvider` + `RefreshProvider`.
  - Pass `AppTopBar` as `topBar`, with `title` "Reception Desk" for Reception and "Staff Workspace" otherwise, `navLabelFor={staffNavLabelFor}` and `loginPath="/staff/login"`.

## 2. Staff Invitations page

- [x] 2.1 `staff-dashboard.tsx`:
  - Lay the page out with `PageContentLayout`.
  - The header is a title row (`<h1>Invitations</h1>` plus the full-label `ExportInvitationsButton` when `canExport`), then `BoardFilterBar`, matching admin's classes.
  - The body wrapper is `flex flex-col lg:h-full`.
  - The loading label is "Loading invitations…".
  - Remove `WorkspaceHeader` and the stale "no Status filter" comment.
- [x] 2.2 `hooks/use-staff-dashboard.ts`:
  - Call `usePageHeader({ description: 'Track visitor invitations, approval status, and check-in progress' })` and `usePageRefresh(...)`, as `useAdminInvitations` does.
  - Remove `signOut` and the push-unregister logic, which now live in the top bar.
- [x] 2.3 Delete `Components/WorkspaceHeader.tsx`. Remove the now-unused `compact` prop from `ExportInvitationsButton`.
- [x] 2.4 Rename the sidebar items: `ReceptionSidebar` "Visits" → "Invitations", `DashboardSidebar` "All visitors" → "Invitations". Keep their keys and routes.

## 3. Register Visitor

- [x] 3.1 `staff-visitor-registration.tsx`:
  - Replace `RegistrationWorkspaceHeader` with a title-only row ("Register Visitor" and its subtitle) and call `usePageHeader({ description })`.
  - Remove the page's own `signOut`.
  - Keep the fixed stepper/action bar and the scrolling form region working.
- [x] 3.2 Delete or trim `RegistrationWorkspaceHeader.tsx` accordingly.

## 4. Admin drag-and-drop fix

- [x] 4.1 In `admin-invitations.tsx`, pass `onDrop={column.status === 'approved' ? requestApprove : column.status === 'denied' ? requestDeny : undefined}` to `KanbanColumn`, as staff does.

## 5. Reconcile pending planning artifacts

- [x] 5.1 In `openspec/changes/move-staff-export-to-header/specs/staff-dashboard/spec.md`:
  - Change the placement to the "Invitations" title row with the full "Export" label.
  - Drop the "before Refresh" text and the compact/icon-only scenario.
  - Run `openspec validate move-staff-export-to-header --strict`.
- [x] 5.2 Re-check `align-staff-board-filters-with-admin` and `add-invitation-export` for "workspace header" wording that contradicts the title-row placement, and fix any you find.

## 6. Verify

- [x] 6.1 Run `npx tsc -b` and `npm run lint`. Both must be clean apart from pre-existing warnings. Do not run prettier.
- [x] 6.2 Browser check at 1440px. Compare `/staff/dashboard` as Reception with `/admin/invitations` as admin:
  - same top bar structure;
  - "Invitations" title row with Export at the right;
  - same filter bar and board positions;
  - one refresh control showing "Updated …";
  - Sign out works and returns to `/staff/login`.
- [x] 6.3 At 1024px and 360px:
  - no horizontal scroll;
  - the phone top bar shows "Invitations";
  - with the Reception role stripped from the profile, no Export button.
- [x] 6.4 Register Visitor at 1440×900: the top bar is shown, there is no duplicate identity block, and the form region scrolls while the stepper and action bar stay fixed.
- [x] 6.5 On the admin board, drag a requested card onto Approved and onto Denied. The approve confirmation and the deny-reason dialog open as on staff. Cancel both, and don't change local data. Cards are no longer draggable (they use Approve/Deny buttons), so this was checked by firing a synthetic drop event at each column on both boards.

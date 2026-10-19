## Context

See proposal.md for the motivation and the specs in this change for the
behavior.

Relevant current state:

- **Admin shell.** `AdminLayout` wraps every `/admin/*` route in
  `PageHeaderProvider` + `RefreshProvider` and passes `AdminTopBar` as
  `AppShell`'s `topBar`.
  - `AdminTopBar` has: `NavMenuButton`; "Organization Admin" plus the page
    description (`md`+), or `adminNavLabelFor(pathname)` on phones;
    `RefreshControl` (reads `RefreshContext`); the bell; the avatar with
    name and role; and Sign out, which unregisters the push device, clears
    the token and goes to `/admin/login`.
  - Admin pages publish to the top bar with `usePageHeader({ description })`
    and `usePageRefresh(...)`, and lay out their body with
    `PageContentLayout`.
- **Staff shell.** `StaffLayout` gives `AppShell` no `topBar`, so
  `AppShell` falls back to `MobileNavBar` (menu button and logo below
  `lg`).
  - Each staff page draws its own header: `WorkspaceHeader` on the board,
    `RegistrationWorkspaceHeader` on Register Visitor.
  - The sidebar is `ReceptionSidebar` ("Dashboard / Visits / My actions")
    for Reception and `DashboardSidebar` ("All visitors / My actions")
    otherwise.
- **Reception Dashboard.** `/reception/dashboard` sits outside
  `StaffLayout` and has its own `ReceptionTopBar` ("Reception Desk").
- **Admin drop targets.** The admin board passes `onMoveToApproved` and
  `onMoveToDenied` but no `onDrop`, so no column accepts a dropped card.

## Goals / Non-Goals

**Goals:**
- One top-bar component, used by both shells, so admin and staff chrome
  can't drift.
- A staff board page whose structure is admin's: `PageContentLayout`,
  title row, filter bar, then board.

**Non-Goals:**
- Moving `/reception/dashboard` under `StaffLayout`, or replacing
  `ReceptionTopBar`. That's a separate page with its own spec; it already
  looks like the shared bar.
- Unifying accent colours, or the sidebars' item sets.
- Any change to the board, cards, modals or API.

## Decisions

### D1. Generalize `AdminTopBar` into a shared `AppTopBar`
`AppTopBar` takes these props:
- `title` ("Organization Admin" / "Reception Desk" / "Staff Workspace");
- `description`, `breadcrumb`, `currentUser`;
- `navLabelFor(pathname)` for the phone title;
- `loginPath` for Sign out.

`AdminTopBar` becomes a thin wrapper, or `AdminLayout` calls `AppTopBar`
directly with the admin values. Either way admin's rendered output is
unchanged. `RefreshControl` and `formatRelativeTime` move with it.
- *Alternative:* a separate `StaffTopBar` copy (rejected: that duplication
  is what lets the two sections drift).

### D2. `StaffLayout` mirrors `AdminLayout`
It wraps its content in `PageHeaderProvider` + `RefreshProvider` and
passes `<AppTopBar title={isReception ? 'Reception Desk' : 'Staff Workspace'}
navLabelFor={staffNavLabelFor} loginPath="/staff/login" …/>`.
`staffNavLabelFor` maps `/staff/dashboard` to "Invitations" and
`/staff/visitors/new` to "My actions", next to the two sidebars'
`resolve…ActiveItem` helpers. Because the bar is in the layout, both
staff routes get it, so Register Visitor's in-page identity/Sign out block
is removed.
- *Alternative:* render the bar only on the board page (rejected: it would
  sit inside `<main>`'s scroll and padding rather than as the shell's fixed
  top bar, and Register Visitor would keep the old look).

### D3. The staff board becomes a structural copy of the admin page body
- `PageContentLayout` with the header `<div class="flex items-center
  justify-between gap-3"><h1>Invitations</h1>{Export}</div>` followed by
  `BoardFilterBar`.
- The body wrapper is `lg:h-full`, the same as admin.
- The retry/loading/error blocks are the same, apart from the accent
  class.
- `useStaffDashboard` calls `usePageHeader({ description })` and
  `usePageRefresh({ refresh, isRefreshing, lastUpdatedAt })`, as
  `useAdminInvitations` does, and drops `signOut`, since the top bar owns
  it, including push-device unregistering.
- Export is the full-label button. `ExportInvitationsButton.compact`
  becomes unused and is removed.
- `WorkspaceHeader.tsx` is deleted.

### D4. The admin drag-and-drop fix is the same expression staff uses
`onDrop={column.status === 'approved' ? requestApprove : column.status === 'denied' ? requestDeny : undefined}`.
No new behavior is specified. `admin-invitations` already requires
drag-to-approve and drag-to-deny.

### D5. Reconcile `move-staff-export-to-header`
That change is unarchived. Its delta places Export "in the workspace
header row, before Refresh". Update it to the title-row placement with the
full label, and drop its compact/icon-only scenario, so archiving it
doesn't contradict this change.

## Risks / Trade-offs

- **Register Visitor's fixed-chrome layout.** Adding a top bar takes
  about 70px from the desktop height its form region scrolls in. → Its
  own title block shrinks (the identity block moves out), so the net
  change is small. The scroll scenarios are re-checked at a 900px-high
  viewport.
- **Sign out now always unregisters the push device on staff pages.** The
  board already did this. Register Visitor's own sign-out didn't. → This
  is more correct, because a signed-out device shouldn't keep receiving
  pushes.
- **Section title wording ("Staff Workspace")** is an assumption for
  non-Reception staff. → It's a single prop value, easy to change in
  review.

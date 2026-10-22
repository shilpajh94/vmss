## Why

The staff and admin invitation boards now share their filter bar, columns,
cards and actions. The pages around the board still look like two
different products:

- **Admin** has a persistent top bar ("Organization Admin", the page
  subtitle, an "Updated just now" refresh indicator, bell, user, Sign out)
  and, below it, an "Invitations" title row holding Export.
- **Staff** draws everything in a single page-level "Visits" header with
  its own Refresh button, and calls the same board "Visits" in its title,
  "Visits"/"All visitors" in its sidebars and "visit requests" in its
  loading text.

There is also a behavior gap. The admin spec requires drag-to-approve and
drag-to-deny "the same as the staff dashboard", but the admin page never
wires the drop targets, so dragging a card there does nothing.

## What Changes

- **A persistent staff top bar, the same as admin's.** `StaffLayout` gains
  a top bar with the same structure and styling as the admin one.
  - The left side shows the section title, with the page description
    below it on `md`+ and the page's own name on phones. The title is
    "Reception Desk" for Reception users, matching their Reception
    Dashboard, and "Staff Workspace" for other staff.
  - The right side has the shared refresh control ("Updated …"), the
    bell, the user's avatar, name and role, and Sign out.
  - It is shared by both staff routes, the board and Register Visitor, so
    each page stops drawing its own identity/Sign out header.
- **The staff board uses the admin page layout.**
  - The page body is `PageContentLayout`, with a title row ("Invitations"
    on the left, Export on the right, full "Export" label as on admin),
    the same filter bar, then the board.
  - The page-level Refresh button is removed. The board publishes its
    refresh to the top-bar control, as the admin board does.
- **"Invitations" everywhere on the staff side:**
  - the staff page title;
  - the Reception sidebar item (was "Visits");
  - the non-Reception sidebar item (was "All visitors");
  - the loading text ("Loading invitations…") and the mobile page name.
- **Register Visitor uses the shared top bar.** It keeps its "Register
  Visitor" title and subtitle as its own title row, and moves its
  identity and Sign out into the top bar. Its form region still scrolls
  on its own between the stepper and the action bar.
- **Admin drag-and-drop fix.** The admin board passes the same `onDrop`
  handlers as staff, so dragging a requested card onto Approved or Denied
  approves it, or asks for a reason and denies it.
- **Unchanged:**
  - the board itself (filters, columns, cards, modals);
  - who sees Export;
  - each section's accent colour (admin teal vs staff accent);
  - the Reception Dashboard page;
  - the sidebar sets (Reception and non-Reception keep their own items,
    only renamed).
- **Pending planning artifacts:** `move-staff-export-to-header` (not yet
  archived) puts Export in the workspace header before Refresh. Its delta
  is updated to the new title-row placement.

## Capabilities

### New Capabilities

_None._

### Modified Capabilities

- `staff-dashboard`:
  - Sidebar/workspace rendering: names and top bar.
  - Signed-in user display: moves to the top bar.
  - Refresh: one shared top-bar control.
  - Compact header and search bar: title row.
  - Adds "The staff Invitations page uses the admin page layout".
- `reception-dashboard`: the Reception sidebar item "Visits" becomes
  "Invitations" in both sidebar requirements.
- `staff-visitor-registration`:
  - The staff shell now includes the shared top bar.
  - The fixed-chrome requirement no longer lists an in-page
    identity/Sign out block.
- `live-data-refresh`: the manual refresh control also covers staff pages
  under `StaffLayout`, via the staff top bar's shared control.

## Impact

- **Shared shell:**
  - `src/presentation/components/AdminTopBar.tsx` is generalized into a
    shared top bar (section title, nav-label resolver, login path).
    `AdminLayout` keeps its current output.
  - `src/presentation/components/StaffLayout.tsx` adds
    `PageHeaderProvider` + `RefreshProvider` and the top bar.
- **Staff pages:**
  - `staff-dashboard.tsx` and `hooks/use-staff-dashboard.ts` use
    `PageContentLayout`, a title row with Export, `usePageHeader` and
    `usePageRefresh`, and drop `signOut`.
  - `WorkspaceHeader.tsx` is deleted.
  - `staff-visitor-registration.tsx` is updated and
    `RegistrationWorkspaceHeader.tsx` is replaced by a title-only row.
  - `ReceptionSidebar.tsx` and `DashboardSidebar.tsx` get the label
    renames, plus a nav-label helper for the mobile top bar.
- **Admin:** `admin-invitations.tsx` gets `onDrop`.
- **Export button:** `ExportInvitationsButton`'s `compact` mode becomes
  unused and is removed.
- **Planning:** the `move-staff-export-to-header` staff-dashboard delta.
- No API change.

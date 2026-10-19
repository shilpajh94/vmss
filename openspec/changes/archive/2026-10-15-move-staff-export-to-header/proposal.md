> **Superseded in part by `unify-staff-and-admin-invitation-pages`:** the
> staff header and `WorkspaceHeader` were replaced by the admin-style title
> row, so Export now sits at the right of the "Invitations" title row with
> its full label, and the compact mode was removed. The spec delta reflects
> the final placement.

## Why

Now that the staff dashboard has the admin board's four filters
(`align-staff-board-filters-with-admin`), the two bars differ only in where
Export sits. Admin puts Export at the end of the page's title row, so its
filter bar holds just the search, the four filters and, when a filter is
set, "Clear filters". On staff, Export is still the last control inside the
filter bar. "Clear filters" and Export then share a second line under the
filters, and the staff bar no longer looks or behaves like the admin one.

## What Changes

- **Export moves to the staff header.** For Reception users, the staff
  dashboard's Export button moves out of the search and filter bar into the
  "Visits" workspace header row, as the first control in its right-hand
  group, before Refresh. This mirrors admin putting Export in its
  "Invitations" title row. Hosts still don't see it.
- **The staff filter bar matches admin.** It holds only the search field,
  Purpose, Registration Type, Status, Source and, when a filter is set,
  "Clear filters". At 1440px the search and the four filters stay on one
  row, and "Clear filters" sits on its own next line, as on admin.
- **Narrow screens.** Below `md` the header's Export shows as an icon
  button labelled "Export" for assistive technology, the way Sign out
  already drops its text. The header then fits on one row at 360px with no
  horizontal scroll. From `md` up it shows the icon and the word "Export".
- **Unchanged:** the Export dialog, its preselected status, its download
  behavior, who sees the button, and the admin page.
- **Reconciling pending planning artifacts.** Two unarchived changes
  describe the old in-bar placement and are updated to match:
  - `add-invitation-export`: its staff-dashboard delta says Export is the
    last control in the bar, and that the dialog always opens on "All
    statuses".
  - `align-staff-board-filters-with-admin`: its "compact search bar"
    requirement places Export in the bar.

## Capabilities

### New Capabilities

_None._

### Modified Capabilities

- `staff-dashboard`: adds "The staff Export button sits in the workspace
  header". It is added rather than modified, because the requirement it
  replaces only exists in the unarchived `add-invitation-export` delta, not
  yet in the main spec. That delta and the
  `align-staff-board-filters-with-admin` delta are edited so all three
  agree before any of them is archived.

## Impact

- `src/presentation/pages/staff-dashboard/Components/WorkspaceHeader.tsx`:
  accepts an optional leading action and renders it before Refresh.
- `src/presentation/pages/staff-dashboard/staff-dashboard.tsx`: passes the
  Export button to `WorkspaceHeader` instead of to `BoardFilterBar`'s
  `trailingAction`.
- `src/presentation/components/invitation-board/ExportInvitationsButton.tsx`:
  optional compact mode (icon only below `md`, with an `aria-label`). The
  admin page keeps the default full label.
- `BoardFilterBar` keeps its `trailingAction` prop. Nothing passes it after
  this change, and removing it is optional cleanup.
- Planning artifacts: the staff-dashboard deltas of
  `add-invitation-export` and `align-staff-board-filters-with-admin`.
- No API change.

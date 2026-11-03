## 1. View switch

- [x] 1.1 Create `InvitationViewToggle` (Board / List, icons) using `SegmentedToggle`
- [x] 1.2 Remember the choice per portal with `useStoredState`, default `board`
- [x] 1.3 Place the toggle in the title row of the admin and staff Invitations pages

## 2. List view

- [x] 2.1 Add a helper that flattens columns, sorts by visit date/time (newest first) and tags each row with its status
- [x] 2.2 Build `InvitationListView`: table from `lg` with avatar/name, tracking ID, status chip, purpose, point of contact, date/time, type; cards below `lg`
- [x] 2.3 Add the row actions menu with the same permission gating and handlers as the board
- [x] 2.4 Clicking a row name/View opens the Visitor Info dialog
- [x] 2.5 Add per-status "Load more" and a loaded-count footer
- [x] 2.6 Add skeleton, empty (filtered and unfiltered) and error states

## 3. Integration

- [x] 3.1 Render board or list on `/admin/invitations` without changing any filter or modal wiring
- [x] 3.2 Render board or list on `/staff/invitations`
- [x] 3.3 Confirm filters persist when switching views

## 4. Verification

- [x] 4.1 Unit test the flatten/sort helper (missing date/time, mixed statuses)
- [x] 4.2 Run `npm run lint`, `npm test`, `npx tsc -b`
- [ ] 4.3 Manually verify default Board, switching, remembered choice, actions, permissions, phone width

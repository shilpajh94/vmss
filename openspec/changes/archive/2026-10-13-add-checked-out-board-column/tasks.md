## 1. Board status model

- [x] 1.1 In `src/presentation/hooks/use-paged-board-columns.ts`, add `'checked_out'` to the `BoardStatus` union and to `BOARD_STATUSES` (between `checked_in` and `denied`), map it to `'checked_out'` in `API_STATUS_BY_BOARD_STATUS`, and add `checked_out: EMPTY_COLUMN` to the initial columns state
- [x] 1.2 In `src/presentation/hooks/use-invitations-board.ts`, insert `{ status: 'checked_out', label: 'Checked-out' }` into `BOARD_STATUS_COLUMNS` between Checked-in and Denied. Update the comment at the `visibleStatuses` memo, which currently cites `checked_out` as a status with no column

## 2. Column presentation

- [x] 2.1 In `src/presentation/components/invitation-board/KanbanColumn.tsx`, add a `checked_out` entry to `ACCENT_CLASSES` using the neutral `text-faint`/`text-muted` tokens (design.md Decision 3)
- [x] 2.2 Add `checked_out: 'No checked-out visits'` to `EMPTY_MESSAGES` in `src/presentation/pages/admin-invitations/admin-invitations.tsx` and `src/presentation/pages/staff-dashboard/staff-dashboard.tsx`
- [x] 2.3 Confirm that neither page passes `onDrop`/`onMoveToApproved`/`onMoveToDenied` for `checked_out`, and that `VisitRequestCard` renders only Visitor Info for a `checked_out` card. No code change is expected; fix it if either is wrong

## 3. Verification

- [x] 3.1 Run `npm run build` (`tsc -b`) and `npm run lint`; both must be clean. Do not run prettier in this repo
- [x] 3.2 Against the local API, open `/admin/invitations` at 1280px and 1024px. Check that five columns render in order, that Checked-out shows cards and the server total, that column scroll/lazy-load works, and that card buttons don't wrap badly. Done: at 1024px the five columns squeezed to ~120px and clipped text, so `KanbanColumn` now has `lg:min-w-[170px]` (design.md Risks). 1024px scrolls horizontally; 1280px and wider are unchanged
- [x] 3.3 On the admin board, select the "Checked-out" status filter. Check that only that column loads and the other four show zero
- [x] 3.4 Open `/staff/dashboard` as a staff user and check that the Checked-out column lists only their own checked-out visits. Check out a checked-in visitor and confirm the card moves from Checked-in to Checked-out after refresh
- [x] 3.5 At 375px width, confirm that the mobile status selector shows a Checked-out tab with its total and that switching to it shows its cards

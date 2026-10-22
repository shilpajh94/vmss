## 1. Prerequisite

- [x] 1.1 Confirm `visit-card-schedule-actions` manual-verification tasks 6.1–6.4 with the user, then archive that change so its Reschedule/Delegate button requirements exist in `openspec/specs/staff-dashboard/spec.md`. This change's REMOVED deltas depend on them.

## 2. Icon button primitive

- [x] 2.1 Remove the now-unused `ActionMenu.tsx` and `MoreHorizontalIcon` that the first build added.
- [x] 2.2 Create `src/presentation/components/ui/IconActionButton.tsx`: a `button` with `aria-label`, `size-8` from `lg` up and `size-10` below, and a CSS-only tooltip (`aria-hidden`) above it that shows on hover and on keyboard focus.

## 3. Card restructure

- [x] 3.1 In `VisitRequestCard.tsx`, rebuild the header row: avatar, then a truncating name over REQ ID. No trigger on the right.
- [x] 3.2 Replace the Purpose and Host rows with one truncated `Purpose · Host` line carrying a `title` of the full text. Move the scheduled date/time line directly beneath it, and remove the bottom divider block.
- [x] 3.3 Split actions:
  - Primary `grid grid-cols-2` row: `canTapApprove`/`canApprove`/`canApproveAndDelegate` + `canTapDeny`, or Check Out spanning both columns.
  - Icon row below it, in order and only when eligible: Visitor info (`InfoIcon`), Reschedule (`CalendarClockIcon`), Edit (`PencilIcon`), Delegate (`UserCheckIcon`). Each has the accessible name "<action> for <REQ ID>".
  - Keep all existing eligibility flags unchanged.
- [x] 3.4 Make the card root `role="button" tabIndex={0}` with an `aria-label`, and have click/Enter/Space call `onVisitorInfoClick`. Keep `stopPropagation` on the primary row and the icon row.
- [x] 3.5 Remove the expanded section and the `isExpanded`/`onToggleExpand`/`isLoadingDetail` props. Show "Approving…" inline in place of the action row while `isApproving`. Tighten to `p-3`/`gap-2`.

## 4. Board state and wiring

- [x] 4.1 In `use-invitations-board.ts`, remove `expandedId`/`toggleExpand`. Make the `?invitationId=` deep-link effect call `viewVisitorInfo`. Drop `loadingDetailId` if nothing else uses it.
- [x] 4.2 Remove the expansion props from `KanbanColumn.tsx`, `staff-dashboard.tsx`, and `admin-invitations.tsx`.
- [x] 4.3 Apply the spacing changes:
  - `KanbanColumn` header `py-2`, column `gap-3`, card list `gap-2`
  - `ResponsiveBoard` desktop `gap-3`

## 5. Staff dashboard header

- [x] 5.1 `WorkspaceHeader.tsx`: reduce the title to `text-2xl` at `md` and tighten the title/subtitle gap.
- [x] 5.2 `SearchActionBar.tsx`: make the search box `h-10 rounded-lg` to match `DropdownFilter`. Lay the bar out so search and both filters share one row from `lg` up (`lg:flex-nowrap`, search `flex-1`) and still wrap below `lg`. Reduce `DropdownFilter` to `sm:w-[200px]`.

## 6. Verification

- [x] 6.1 `npm run build` and `npm run lint` pass.
- [x] 6.2 At 1440×900 on `/staff/dashboard`, check that at least three Requested cards are visible per column. Check that Approve/Deny share a row, that no host label wraps, and that the scheduled time sits under the meta line.
- [ ] 6.3 Check the icon row per column: Requested, Approved, Checked-in, Checked-out (Visitor info only), Denied. Check that each icon opens the same modal its old button did, and that Edit shows on Requested and Approved cards.
- [ ] 6.4 Check keyboard use: Tab to a card and press Enter to open Visitor Info. Tab through the icon buttons and check that each shows its tooltip on focus and activates with Enter.
- [ ] 6.5 Check that clicking a card body opens Visitor Info, and that Approve/Deny/Check Out and the icon buttons do not also open it. Check that the `?invitationId=` deep link opens Visitor Info.
- [ ] 6.6 At 360px and in the tabbed mobile view, check that there is no horizontal scroll, tap targets (including the icon buttons) are at least 40px, and the icon row doesn't overflow the card.
- [ ] 6.7 Repeat 6.2–6.5 on `/admin/invitations`.
- [x] 6.8 Run `npm run screenshots` and compare the before/after board captures. Add a CHANGELOG entry noting that cards now open Visitor Info on click.

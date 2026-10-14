## Context

The board is one set of components shared by `/staff/dashboard` and `/admin/invitations`:

- `ResponsiveBoard`: five columns side by side from `lg` up, one tabbed column below.
- `KanbanColumn`: a pinned header and a lazily paged, internally scrolling card list.
- `VisitRequestCard`.

All board state lives in `use-invitations-board.ts`. Today a card's root `onClick` toggles `expandedId`. The expanded section only repeats the "Level X/Y · Pending" badge as a sentence, and the badge is already visible on the collapsed card because the hook preloads detail for every loaded Requested/Approved card.

Each action is its own `flex-1 min-w-[92px]` button inside a `flex-wrap` row. At the column width of a five-column desktop board (~260px), each button wraps onto its own line, which is where the stacked look in the screenshot comes from.

`?invitationId=` deep links (push notifications) currently set `expandedId`.

The web repo has no unit-test runner. Verification is `npm run build` (type check), `npm run lint`, and the Playwright `npm run screenshots` script, plus manual checks.

## Goals / Non-Goals

**Goals:**
- At a 1440×900 desktop viewport, show at least three typical Requested cards per column without scrolling. Today it shows about 1.5.
- Keep every existing action reachable, with identical modals and rules. Only where an action is triggered changes.
- Keep the icon buttons fully keyboard- and touch-operable (responsive-layout "Controls Are Touch-Operable").

**Non-Goals:**
- Changing column count, order, colours, the pinned headers, or lazy paging.
- Changing the admin Invitations page header, which is already a compact single row.
- Restyling the modals themselves.
- Any API change.

## Decisions

### 1. Primary-vs-secondary split is computed in the card, from the existing `can*` flags

`VisitRequestCard` already derives:

- `canTapApprove`, `canTapDeny`, `canApprove`, `canApproveAndDelegate`
- `canReschedule`, `canEdit`, `canDelegate`
- `onCheckOutClick` presence

Labelled buttons are the first group plus Check Out. The icon row gets Visitor info plus `canReschedule`, `canEdit`, `canDelegate`.

No eligibility logic moves or changes, so the subtle Reception-step and workflow-rules-loaded gating stays exactly as it is today. Primary buttons render in a `grid grid-cols-2 gap-2` row so that Approve/Deny always pair up; a lone Check Out spans both columns.

*Alternative considered:* configuring the action list per column in `KanbanColumn`. Rejected because the card's eligibility depends on per-request detail, not just the column.

### 2. Icon buttons via a small `IconActionButton` component, not a menu

*Revised during review.* The first build put the secondary actions in a "⋯" menu. In testing, the user couldn't find Edit there, so every action is now visible on the card as an icon button.

`IconActionButton` (`components/ui/`) takes these props:

- `icon`
- `label`: the action name, shown as the tooltip
- `accessibleName`: "<label> for <REQ ID>"
- `onClick`

It renders a `button` with `aria-label`, at `size-8` from `lg` up and `size-10` below. The tooltip is a CSS-only `span` positioned above the button. It is shown on `group-hover` and on `group-focus-visible`, so it also appears on keyboard focus, which `title=` alone wouldn't do. The tooltip has `aria-hidden`, because the `aria-label` already names the action.

Icons, all already in `icons.tsx`:

| Action | Icon |
| --- | --- |
| Visitor info | `InfoIcon` |
| Reschedule | `CalendarClockIcon` |
| Edit | `PencilIcon` |
| Delegate | `UserCheckIcon` |

The icon row goes along the bottom of the card, left-aligned, with `gap-1`. It sits below the primary button grid. On cards without primary buttons (Approved, Checked-out, Denied), it is the card's only control row.

The row is at the bottom of the card, so a tooltip above it always stays inside the card. The column scroll area can't clip it, and no flip logic is needed.

*Alternatives considered:*
- Keeping the "⋯" menu. Rejected: Edit wasn't discoverable.
- Making only Edit a labelled button. Rejected: the user chose icon buttons, and a third labelled button would crowd the Approve/Deny row.

### 3. Card click → Visitor Info, and the expansion state is retired

The card root becomes `role="button" tabIndex={0}` with `onClick` and an `onKeyDown` handler for Enter/Space that call `onVisitorInfoClick`. It is not a `<button>`, because it contains buttons and a `<button>` can't legally nest them.

Both the primary-button row and the icon row call `stopPropagation()`, so their clicks don't bubble up to the card.

Removed:

- `expandedId`, `toggleExpand`, and `isExpanded`/`onToggleExpand`/`isLoadingDetail` from the hook, `KanbanColumn`, the card, and both pages
- the expanded-section JSX

The deep-link effect calls `viewVisitorInfo(invitationId)` instead of `setExpandedId`. `viewVisitorInfo` already force-loads the detail and toasts on failure.

`loadingDetailId` is kept only if something else still reads it; otherwise it is removed.

*Alternative considered:* keeping expansion and making only a "Visitor info" link open the modal. Rejected because the user chose card-click-opens-info, and expansion added nothing the badge doesn't show.

### 4. Card layout

- **Header row:** avatar on the left. Next to it, a `min-w-0` column holding the name (bold, truncate) over the REQ ID (11px, faint).
- **Meta line:** `Purpose · Host` in one `truncate` span. The `title` attribute holds the full string for the hover requirement.
- **Next lines:** the scheduled line (`CalendarClockIcon` + date/time), then the Level badge, then the primary action grid, then the icon row.
- **Spacing:** padding goes from `p-4` to `p-3` and gaps from `gap-3` to `gap-2`.
- **Removed:** the bottom divider and the scheduled block.
- **"Approving…":** shown as a small inline status in place of the action grid while `isApproving`.

### 5. Column and header spacing

- **`KanbanColumn`:** header `py-3` → `py-2`, column `gap-4` → `gap-3`, card list `gap-3` → `gap-2`.
- **`ResponsiveBoard` desktop:** `gap-4` → `gap-3`.
- **`WorkspaceHeader`:** title `md:text-[28px]` → `md:text-2xl`, subtitle gap reduced.
- **`SearchActionBar`:** the search box becomes `h-10 rounded-lg py-0`, the same height as `DropdownFilter`. Its layout becomes `flex-col sm:flex-row sm:flex-wrap lg:flex-nowrap`, so search and filters share one row from `lg` up. `DropdownFilter` drops to `sm:w-[200px]`.

These are Tailwind class edits only. No new theme tokens.

### 6. Admin spec requirement keeps its header name

`admin-invitations`' "Card expand, approve, reschedule, and deny behave the same as the staff dashboard" is MODIFIED in place, not renamed. A RENAMED + MODIFIED pair on the same requirement is easy to get wrong at archive time. The stale word "expand" in the header can be cleaned up in a later spec-only edit.

## Risks / Trade-offs

- **Icons are less self-explanatory than labels.** → Each icon has a tooltip on hover and focus, and an accessible name. The icons always appear in the same order and position.
- **Habit change: staff who clicked a card to see approval progress now get the Visitor Info modal.** → The same information is on the badge, and the modal is a richer view of that visit. Call it out in the release note or CHANGELOG.
- **The pending `visit-card-schedule-actions` change must be archived first**, or this change's REMOVED requirements won't match the main spec at archive time. → Task 1.1 archives it, after confirming its manual-verification tasks.
- **The card is `role="button"` with nested buttons**, which can be noisy for screen readers. → Give the card an `aria-label` of "Open visitor info for <name>, <REQ ID>" so its name stays short and isn't the concatenation of all its text.

## Migration Plan

This is a frontend-only deploy. Rollback is reverting the commit. There is no data or API migration.

## Open Questions

- Exact date/time display format on the scheduled line: keep the current raw `YYYY-MM-DD HH:mm`, or switch to a friendlier "14 Oct, 10:30". This is cosmetic and doesn't affect the specs. Default to keeping the current format unless the reviewer asks otherwise.

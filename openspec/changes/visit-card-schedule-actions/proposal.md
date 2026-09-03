## Why

On the staff dashboard and admin invitations Kanban boards, Reschedule and Delegate are hidden inline forms that only appear once a card is expanded, so staff can't tell at a glance that these actions exist, and taking either action clutters the same card that shows approval-step progress. Separately, the board already promises to show each request's scheduled visit date/time on its card, but the card currently only renders the submission timestamp — the actual scheduled visit time is never shown.

## What Changes

- Replace the inline "Reschedule visit" and "Delegate this step" panels (shown today only on an expanded, eligible card) with dedicated **Reschedule** and **Delegate** buttons always visible on the card footer for eligible requests.
- Activating either button opens a modal dialog containing that action's form (date/time fields for Reschedule; role-scoped host picker for Delegate), instead of expanding inline within the card.
- Add the scheduled visit date/time (`preferredVisitDate` / `preferredVisitTime`) to the visit-request summary payload and render it on every card, alongside the existing submitted-at timestamp.
- Card expansion keeps showing approval-step progress only; it no longer also hosts the reschedule/delegate forms.

## Capabilities

### New Capabilities

(none)

### Modified Capabilities

- `staff-dashboard`: the reschedule action moves from an inline expanded-card form to a button-triggered modal; a new Delegate button + modal action is introduced for cards with a current approval step; cards render the scheduled visit date/time.

## Impact

- `src/domain/entities/visit-request-summary-schema.ts`: add `preferredVisitDate` / `preferredVisitTime` to `VisitRequestSummarySchema`.
- `src/presentation/components/invitation-board/VisitRequestCard.tsx`: replace inline reschedule/delegate panels with buttons + a shared modal component; render scheduled date/time.
- `src/presentation/hooks/use-invitations-board.ts`: reschedule/delegate action state (open modal, submit, close on success) replaces expand-coupled state where needed.
- Shared by both `staff-dashboard` (`/staff/dashboard`) and `admin-invitations` (`/admin/invitations`), which reuses the same board/card components — admin-invitations' spec already defers to staff-dashboard's card behavior unchanged, so no separate delta is needed there.

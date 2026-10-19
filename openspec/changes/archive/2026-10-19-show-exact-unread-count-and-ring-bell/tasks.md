## 1. New-arrival signal

- [x] 1.1 In `src/presentation/context/notification-center-context.tsx`,
  work out "any unseen item" in `refresh`, and increment a new
  `newArrivalCount` state when it is true (never on the first load).
  Keep `onInvitationActivity` behaviour unchanged.
- [x] 1.2 Add `newArrivalCount` to the context value type and the
  `useMemo` value and dependencies.

## 2. Motion

- [x] 2.1 Add `--motion-attention: 700ms` to `src/styles/theme.css`, with
  a comment that it is ui-motion's bell-ring exception.
- [x] 2.2 Add `@keyframes motion-bell-ring` and a `.motion-bell-ring`
  class to `src/styles/index.css` (design.md Decision 3).

## 3. Bell

- [x] 3.1 In `NotificationBell.tsx`:
  - always render the badge with the exact count, and remove the `'9+'`
    cap
  - use neutral styles at 0 and alert styles above 0
  - add `tabular-nums`
  - re-anchor the badge so extra digits grow outward (design.md
    Decision 4)
- [x] 3.2 Make the accessible name always
  `Notifications, ${unreadCount} unread`.
- [x] 3.3 Wrap `BellIcon` in a span keyed by `newArrivalCount`, with
  `motion-bell-ring` applied only when the count is above 0.

## 4. Verification

- [x] 4.1 Run `npm run build` and `npm run lint`. Do not run prettier.
- [x] 4.2 Add `e2e/test_notification_bell.py`:
  - after "Mark all read", the badge reads "0" and the accessible name is
    "Notifications, 0 unread"
  - when more than nine notifications are made unread through the API,
    the badge shows the exact number
  - when a new notification arrives while the page is open (an
    invitation created by another role, then the next refresh), the
    bell's icon wrapper gets the ring class, and it does not get it on
    the first load after sign-in
- [x] 4.3 Check the top bar at 360px, 768px, and 1440px with counts 0, 7,
  12, and 143: the badge is fully visible, the icon is recognisable, and
  the bar doesn't wrap. Repeat with reduced motion emulated and confirm
  there is no ring.
- [x] 4.4 Run `npm run e2e` for the new test plus `test_live_dashboards.py`
  and `test_invitation_lifecycle.py`. Do not run it at the same time as
  API pytest.

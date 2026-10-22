## 1. Bell

- [x] 1.1 In `NotificationBell.tsx`, set `UNREAD_REMINDER_INTERVAL_MS`
  to `15_000` and update its comment.
- [x] 1.2 Add a `ring()` helper that bumps `ringKey` only when the
  latest `unreadCount` (held in a ref) is above 0. Route both the
  new-arrival effect and the reminder timeout through it (design.md
  Decision 2).

## 2. Verification

- [x] 2.1 Run `npm run build` and `npm run lint`. Do not run prettier.
- [x] 2.2 Update `e2e/test_notification_bell.py`:
  - change the reminder test's fake-clock steps to 15s: the first ring
    at about 16s, the next about 15s later, and stillness for 20s after
    "Mark all read"
  - add a check that, with 0 unread, the bell's icon wrapper is never
    remounted across a feed refresh, using a refresh that brings in an
    already-read notification
- [x] 2.3 Run the bell, live-refresh, and lifecycle e2e tests, then the
  full `npm run e2e` suite. Do not run it at the same time as API pytest.

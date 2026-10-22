## Why

The bell's reminder ring for unread notifications comes every 30
seconds, which is easy to miss at a busy front desk; 15 seconds keeps
the cue noticeable. The bell should also be completely still when
nothing is unread. The reminder already stops at zero, but a new-arrival
ring can still play at zero: when a refresh brings in a notification
that was already read, for example in another tab.

## What Changes

- **15-second reminder:** while at least one notification is unread and
  the tab is visible, the bell rings again every 15 seconds instead of
  30. The other rules stay as they are:
  - a new-arrival ring restarts the wait
  - no reminder while the popover is open or the tab is hidden
  - no movement with reduced motion
- **No animation at zero:** when the unread count is 0, the bell never
  animates, neither as a reminder nor for a newly arrived but already-read
  notification.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `app-shell`:
  - "The notification bell rings when a new notification arrives" gains
    a no-ring-at-zero rule.
  - "The notification bell repeats its ring while notifications stay
    unread" changes its interval from 30 to 15 seconds.

## Impact

- **Code**: `src/presentation/components/notification-bell/NotificationBell.tsx`
  (the interval constant, and the zero guard on the ring trigger).
- **Tests**: `e2e/test_notification_bell.py` updates its reminder timings
  to 15s and adds a check that nothing animates at zero.
- **API**: no change.

## Context

`NotificationBell.tsx` drives every ring through one local `ringKey`.
Each increment remounts the icon wrapper, which replays the
`motion-bell-ring` animation. Two things bump it:
- **New arrivals:** an effect that fires when the notification center's
  `newArrivalCount` changes after mount.
- **Reminders:** a timeout scheduled
  `UNREAD_REMINDER_INTERVAL_MS` (30 000) after the last ring, armed only
  while `unreadCount > 0`, the popover is closed, and the tab is visible.

The new-arrival effect doesn't look at `unreadCount`.

## Goals / Non-Goals

**Goals:**
- A 15s reminder.
- Zero unread means zero animation, enforced at the one place a ring
  starts.

**Non-Goals:**
- Changing the ring animation itself, the 60s feed poll, or any other
  reminder condition.

## Decisions

### 1. Halve the constant

`UNREAD_REMINDER_INTERVAL_MS = 15_000`. The timer already measures from
the last ring, so a new-arrival ring still restarts the wait with no
other change.

### 2. Guard at the ring trigger, not in each caller

A small `ring()` helper checks the latest unread count, held in a ref,
before bumping `ringKey`. Both the new-arrival effect and the reminder
timeout go through it, so "no animation at zero" holds for every current
ring source and any future one.
- **Why a ref:** the new-arrival effect runs after the render where both
  `newArrivalCount` and `unreadCount` have been set from the same
  refresh, so the ref already holds the post-refresh count.
- **Arrival not lost:** the seen-arrival ref is still updated when the
  guard skips a ring, so that arrival never rings later.
- *Alternative considered*: checking `unreadCount > 0` inside the
  new-arrival effect only. The reminder already checks it separately, so
  there would be two copies of one rule.

## Risks / Trade-offs

- [A ring every 15s is twice as frequent and may feel insistent] → this
  is what was requested. Reading the notifications, or "Mark all read",
  stops it at once.

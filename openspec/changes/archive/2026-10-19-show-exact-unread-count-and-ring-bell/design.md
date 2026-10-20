## Context

`NotificationBell.tsx` (rendered once, in the shared `AppTopBar`) reads
`notifications`, `unreadCount`, `markRead`, and `markAllRead` from
`NotificationCenterProvider`.
- `unreadCount` comes from `GET /notifications/unread-count`, so it is
  already exact.
- The bell hides the badge when the count is 0, and renders `'9+'` above
  9 (`NotificationBell.tsx:143`).
- The provider refreshes on sign-in, every 60s while the tab is visible,
  on `visibilitychange`, and when `PushNotificationsProvider` gets a
  foreground push.
- It already keeps a `seenIdsRef` set. The first load only fills it, and
  later refreshes compare against it to fire `onInvitationActivity` for
  unseen invitation-linked items.

Motion timing lives in `src/styles/theme.css` (`--motion-fast`,
`--motion-standard`, `--motion-slow`), and keyframes and `.motion-*`
classes live in `src/styles/index.css`. A global
`prefers-reduced-motion` block cuts every animation to 0.01ms.

## Goals / Non-Goals

**Goals:**
- An always-visible, exact badge, with a neutral zero state.
- One ring per refresh that brings in something unseen, driven by the
  provider's existing seen-ids tracking.

**Non-Goals:**
- Sound, a browser-tab title counter, or a favicon badge.
- Ringing for notifications that were already unread when the session
  started.
- Changing the API, the poll interval, or the push flow.

## Decisions

### 1. The provider exposes a `newArrivalCount` counter

Inside `refresh`, the provider already works out which feed items are
unseen. It gains a broader flag: *any* unseen item, not only
invitation-linked ones. When that flag is set, it increments a
`newArrivalCount` state, which the context value exposes. The first load
can't trigger it, because `seenIdsRef` starts `undefined`. Sign-out
clears `seenIdsRef` (it already does), so the next sign-in's first load
is silent again.
- A counter rather than a boolean, because each increment is a distinct
  trigger. The bell doesn't need to reset anything.
- The existing `onInvitationActivity` listeners stay exactly as they are.
- *Alternative considered*: comparing `unreadCount` before and after.
  The count can rise without anything new (a read was undone because a
  mark-read failed and the refetch restored it), and it can stay flat
  when one item is read while another arrives. Seen ids track new
  arrivals directly.

### 2. The bell restarts the ring by remounting a keyed wrapper

The bell wraps `BellIcon` in a `<span key={newArrivalCount}>`. It gets
the `motion-bell-ring` class only while `newArrivalCount > 0`, so the
initial render doesn't ring. Each increment remounts the span, which
restarts the CSS animation. A ring that is still playing simply starts
again, so rings never queue, and no timers or `animationend` bookkeeping
are needed.

### 3. Ring motion: a CSS keyframe with its own token

`theme.css` adds `--motion-attention: 700ms`, the ui-motion exception.
`index.css` adds `@keyframes motion-bell-ring`: rotation about the bell's
top-centre (`transform-origin: 50% 10%`), damped swings
0 → 14° → −12° → 8° → −5° → 2° → 0. `.motion-bell-ring` applies it once
with `var(--ease-motion-out)`. Rotating only the icon wrapper leaves the
badge still and readable, and changes no layout. The existing global
reduced-motion block already makes it instant, so it needs no extra
rule.

### 4. Badge: always rendered, two styles, digits grow outward

- **Rendering:** the badge is always rendered with
  `String(unreadCount)`. A count of 0 uses neutral tokens
  (`bg-border text-text-muted`); above 0 uses `bg-danger text-white`.
  `tabular-nums` and the existing `min-w-4 px-1` let it widen for
  2–4-digit counts.
- **Position:** anchored by its left edge at about the bell's centre-right
  instead of `-right-0.5`. More digits extend outward into the gap before
  the avatar instead of across the icon. The button keeps
  `overflow: visible`, so nothing clips.
- **Accessible name:** always `Notifications, ${unreadCount} unread`.
- **"Mark all read":** stays hidden at zero, since there is nothing to
  mark.

## Risks / Trade-offs

- [Several tabs open at once each ring for the same notification] →
  that's acceptable, since each tab is a separate view the user may be
  looking at.
- [A 4-digit count (≥1000) at 360px could crowd the avatar] → the badge
  sits in the existing gap and the top bar already drops non-essential
  items below `md`. The 360px check in the tasks covers it.
- [A permanent "0" adds visual noise] → it uses muted neutral tokens, the
  same weight as the bell background, so only a non-zero count draws the
  eye.

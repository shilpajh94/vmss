## Why

Toasts are pinned to the top-right corner (`fixed top-4 right-4`), which is
exactly where the top bar keeps the refresh control, notification bell and
user avatar, so every toast hides them until it expires. When a burst of
foreground push notifications arrives (10+ invitations created at once),
each one becomes its own toast and they stack down the page one by one,
covering the board and burying the action the user came to do. Separately,
the top-bar refresh icon uses the stock `animate-spin` loop: it starts at
full speed and snaps to a stop mid-turn when the refresh finishes, which
looks abrupt next to the rest of the app's motion.

## What Changes

- Move the toast viewport to the bottom-right corner on desktop and the
  bottom edge on phones, so no toast ever covers the top bar. Toasts slide
  in from that edge and the newest sits closest to it.
- Cap the toast viewport at three visible toasts. Further toasts wait in a
  queue and appear as visible ones leave; an error is never dropped.
- Group foreground push notifications: a push that arrives while a push
  toast is already showing (or within a short burst window) folds into a
  single summary toast — "5 new notifications" — whose count updates in
  place instead of adding a new toast. Activating the summary opens the
  notification bell's panel, where every item is listed. A lone push still
  shows its own message and still opens its invitation when clicked.
- Pause a toast's auto-dismiss timer while the pointer hovers it or it has
  keyboard focus, so a user reading or reaching for a toast doesn't lose it.
- Replace the refresh icon's spin with a refined motion: on activation the
  icon accelerates into its rotation, turns smoothly while the refresh runs,
  and when the refresh finishes it decelerates and settles exactly on an
  upright resting position instead of stopping mid-turn. Hovering the idle
  control gives a small rotation nudge as an affordance. Reduced-motion
  users keep a plain constant-speed spin (it is a status indicator) with no
  easing flourishes.

## Capabilities

### New Capabilities

_None._

### Modified Capabilities

- `notifications`: the viewport's placement, the three-toast cap with
  queueing, hover/focus pausing of auto-dismiss, and grouping of burst push
  notifications into one summary toast that opens the bell panel.
- `ui-motion`: toasts slide in from the bottom edge instead of the top; new
  requirement for the refresh control's accelerate–spin–settle motion.
- `live-data-refresh`: the manual refresh control's spin settles to an
  upright resting angle when the refresh finishes rather than stopping
  wherever it is.

## Impact

- Web only (`VMMS_WEB`); no API change.
- `src/presentation/components/toast/` — `toast-context.tsx` (queue, cap,
  grouping key, pause), `ToastViewport.tsx` (bottom anchoring), `Toast.tsx`
  (hover/focus pause, summary count).
- `src/presentation/components/push-notifications/PushNotificationsProvider.tsx`
  — routes pushes through the grouped toast.
- `src/presentation/context/notification-center-context.tsx` and
  `notification-bell/NotificationBell.tsx` — a shared "open the panel"
  request so the summary toast can open the bell.
- `src/presentation/components/AppTopBar.tsx` (`RefreshControl`) and
  `src/styles/index.css` — new refresh-spin motion and the bottom-anchored
  toast slide keyframes.
- Builds on the uncommitted `AppTopBar`/`NotificationBell` work currently in
  the working tree (manual-only spin, live clock, bell ring); it must land
  first or together.
- Existing e2e/unit tests that assert toast position or `animate-spin` on the
  refresh icon need updating.

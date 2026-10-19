## Why

The notification bell in the top bar has three problems:
- It shows no badge at all when everything is read, so staff can't tell
  "nothing unread" from "badge failed to load".
- It caps the badge at "9+", so someone with 10 unread and someone with
  80 see the same thing.
- A new notification arrives silently, unless the browser shows a push
  pop-up.

The unread count already comes exact from the API, so all three are fixes
to how the bell presents it.

## What Changes

- The bell always shows its unread badge. At zero it shows "0" in a
  muted, neutral style, not the red alert style.
- The badge shows the exact unread count (for example "12" or "143"),
  never "9+". It widens to fit the digits without overlapping or clipping
  the bell, at every supported width.
- When a notification arrives that the bell hasn't seen before (picked
  up by the 60-second poll, a foreground push, or the tab becoming
  visible again), the bell plays a single ring of about 700ms. The first
  load after sign-in doesn't ring, and a refresh with nothing new doesn't
  ring. Reduced-motion users get no ring; the updated count still shows.
- The bell's accessible name always states the count, including
  "Notifications, 0 unread".
- **Motion rule change:** `ui-motion`'s "no one-off animation longer
  than 300ms" gains one named exception for this new-notification ring.
  All other animations keep the 300ms cap.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `app-shell`: adds requirements for the shared top bar's notification
  bell: an unread badge that is always shown, with the exact count and a
  zero state, and the new-notification ring. (The `notifications` spec
  covers toast pop-ups, not the bell.)
- `ui-motion`: "Animations use one shared timing scale" allows the
  new-notification bell ring as the one exception to the 300ms cap.

## Impact

- **Code**:
  - `src/presentation/components/notification-bell/NotificationBell.tsx`:
    badge rendering, accessible name, and triggering the ring.
  - `src/presentation/context/notification-center-context.tsx`: exposes
    a "new notification arrived" signal, using the seen-ids tracking it
    already has.
  - `src/styles/theme.css` and `src/styles/index.css`: a ring duration
    token and keyframes.
- **API**: no change. `GET /notifications/unread-count` already returns
  the exact number.
- **Where it shows**: the bell is shared by the admin, staff, and
  reception top bars, so all three get the change.

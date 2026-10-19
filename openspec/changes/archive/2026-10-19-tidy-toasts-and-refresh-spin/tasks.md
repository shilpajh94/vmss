## 1. Toast viewport placement

- [x] 1.1 Move `ToastViewport` to `fixed bottom-4 right-4 left-4 sm:left-auto`, newest toast last (closest to the edge), and swap the per-toast spacing wrapper from `pb-2` to `pt-2` so a leaving slot collapses toward the edge
- [x] 1.2 Add a `motion-slide-in-bottom` keyframe in `src/styles/index.css` and use it for `.motion-toast[data-state="open"]` below 640px (keep `motion-slide-in-right` at ≥640px); drop the top-slide usage
- [x] 1.3 Verify at 1440px and 390px that a visible toast leaves the top bar's refresh control, bell and avatar uncovered and clickable

## 2. Visible cap, queue and timers

- [x] 2.1 In `toast-context.tsx`, stop scheduling auto-dismiss in `show`; render only the first three non-closing items and keep the rest queued in insertion order
- [x] 2.2 Move the auto-dismiss timer into `Toast` (armed on mount, so queued toasts start their duration only once visible), keeping the per-variant durations
- [x] 2.3 Pause the timer on `pointerenter`/`focusin` and re-arm with `max(remaining, 2000ms)` once neither pointer nor focus is inside the toast

## 3. Push grouping

- [x] 3.1 Add `groupKey` and `groupSummary` to `ToastOptions`; in the reducer, an `ADD` whose `groupKey` matches a live (open or queued, not closing) item increments its `groupCount`, applies the summary message/onClick, and bumps `groupVersion` instead of adding an item
- [x] 3.2 Make `Toast` restart its auto-dismiss timer when `groupVersion` changes, without remounting (same key, no entry animation)
- [x] 3.3 Give the summary text a polite live region whose announced copy is debounced (~1s) so a burst is announced once or twice, not per push
- [x] 3.4 Add `openPanel()` and `panelOpenRequest` to `NotificationCenterContext`; make `NotificationBell` open its popover when the counter changes after mount
- [x] 3.5 In `PushNotificationsProvider`, pass `groupKey: 'push'` and a summary of "N new notifications" whose onClick calls `openPanel()`; a lone push keeps its own message and invitation link

## 4. Refresh icon motion

- [x] 4.1 Add a `useRefreshSpin` hook (Web Animations API) that ramps in with an ease-in turn, chains an infinite linear loop at matched speed, and on stop reads the current angle and eases out to the next whole turn, then resets to 0°
- [x] 4.2 Handle a re-click during the settle by cancelling it and resuming the loop from the current angle without a ramp or jump
- [x] 4.3 Wire the hook into `RefreshControl` in `AppTopBar.tsx` in place of the `animate-spin` class, keeping the existing manual-only pending logic and 15s spin limit
- [x] 4.4 Add the idle hover/focus-visible nudge (≈30° clockwise, matching the `refresh-cw` icon) on an inner wrapper, disabled while spinning and only under `prefers-reduced-motion: no-preference`
- [x] 4.5 Under reduced motion, fall back to the constant `animate-spin` class while pending and show upright immediately on finish

## 5. Tests and checks

- [x] 5.1 Update `e2e/test_live_refresh.py` / `e2e/test_motion_and_loading.py` to assert the refresh icon is rotating while a manual refresh is pending and its computed transform is upright afterwards, instead of checking for `animate-spin`
- [x] 5.2 Add e2e coverage: toast appears bottom-right and the bell stays clickable; a fourth toast waits until one of three leaves; hovering a toast keeps it past its duration
- [x] 5.3 Add e2e coverage for push grouping (simulate several foreground pushes, assert one "N new notifications" toast whose click opens the bell panel) and that action feedback toasts are not merged; update `e2e/test_notification_bell.py` for any changed selectors
- [x] 5.4 Run `npm run lint`, the TypeScript build, and `npm run e2e`; check the toast and refresh motion manually in light and dark themes and with reduced motion enabled

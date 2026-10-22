## Context

- Toasts: `ToastProvider` (`components/toast/toast-context.tsx`) keeps an
  unbounded array in a reducer, schedules a fixed `setTimeout` auto-dismiss
  per toast on `show`, and renders `ToastViewport` as
  `fixed top-4 right-4` — the same corner as the top bar's refresh control,
  bell and avatar. Enter/exit motion is CSS in `index.css` (`.motion-toast`,
  a grid-rows collapse plus `motion-slide-in-top` / `-right`).
- Pushes: `PushNotificationsProvider` calls `toast.info(message, { onClick })`
  once per foreground FCM message and then `notificationCenter.refresh()`,
  so the bell's feed already holds every pushed item.
- Bell: `NotificationBell` owns its popover's `isOpen` as local state; there
  is no way for anything else to open it.
- Refresh icon: `RefreshControl` in `AppTopBar.tsx` toggles Tailwind's
  `animate-spin` on `isManualRefreshPending` (uncommitted work in the tree
  already limits the spin to user-started refreshes). Removing the class
  drops the icon back to 0° instantly — the "rolls and stops" the user sees.
- One global reduced-motion rule in `index.css` collapses all animations
  except `.animate-spin` and `.progress-indeterminate`.

## Goals / Non-Goals

**Goals:**
- Toasts never cover the top bar; bursts never flood the screen.
- A refresh icon motion with a soft start and a clean upright landing.
- No new dependency; reuse the existing motion tokens (`--motion-*`,
  `--ease-motion-*`).

**Non-Goals:**
- Changing the bell panel's contents, the push payload, or the API.
- Grouping non-push toasts (e.g. collapsing repeated identical errors).
- A swipe-to-dismiss gesture on phones.

## Decisions

### 1. Bottom-right anchoring, not "top-right below the top bar"
Move the viewport to `fixed bottom-4 right-4 left-4 sm:left-auto` and render
the list `flex-col` with newest last (closest to the edge). Entry slides in
from the right (≥640px) or up from the bottom (`motion-slide-in-bottom`, a
new keyframe mirroring `motion-slide-in-top`).
*Alternative*: keep top-right but offset by the top bar's height. Rejected —
it then covers the page's own header row (filters, Export) and has to track
the top bar's responsive height; bottom-right is clear of both and is the
convention for transient feedback.
The collapse-on-exit grid trick still works; the per-toast spacing wrapper
moves from `pb-2` to `pt-2` so a leaving toast's slot collapses toward the
edge and the rest glide down into it.

### 2. Queue lives in the reducer; timers start on visibility
State becomes `{ items: ToastItem[] }` where the first `MAX_VISIBLE = 3`
non-closing items render and the rest are queued (FIFO by insertion). The
auto-dismiss timer is no longer scheduled in `show`; instead each rendered
`Toast` owns its timer (`useEffect` on mount), which is what makes both
"start when visible" and hover/focus pause straightforward: the toast tracks
`remainingMs`, clears its timeout on `pointerenter`/`focusin`, and on
`pointerleave`/`focusout` (when neither is active) re-arms with
`max(remainingMs, 2000)`.
*Alternative*: keep timers in the provider keyed by id. Rejected — pause
needs per-toast DOM events anyway, and provider-held timers for queued items
would expire before they're seen.

### 3. Push grouping via a group key on the toast
`ToastOptions` gains `groupKey?: string` and `groupSummary?: (count) =>
{ message, onClick }`. On `ADD` with a `groupKey` that matches a live
(open or queued, not closing) item, the reducer increments that item's
`groupCount`, swaps in the summary message/onClick, and bumps a
`groupVersion` the rendered `Toast` uses to restart its timer — no new item,
no re-entry animation (same React key). `PushNotificationsProvider` passes
`groupKey: 'push'` and a summary of
`` `${n} new notifications` `` whose onClick calls
`notificationCenter.openPanel()`.
A push that arrives after the group's toast has started closing begins a
new group (matches the spec's "new burst after the summary leaves").
The "within two seconds" scenario falls out naturally: the first push's
toast is still live when the rest arrive.
*Alternative*: debounce pushes in the provider and emit one toast after a
quiet period. Rejected — it delays the first notification for everyone to
handle the rare burst.

### 4. Opening the bell from outside: a request counter in context
`NotificationCenterContext` gains `openPanel(): void` and
`panelOpenRequest: number`. `NotificationBell` watches the counter
(ignoring its value at mount, the same pattern as `newArrivalCount`) and
sets `isOpen = true`. A counter rather than a boolean so repeated requests
always re-trigger and the bell keeps sole ownership of closing.

### 5. Live-region announcements for the summary
The summary toast's text node is `aria-live="polite"` with
`aria-atomic="true"`; the count update is applied immediately for sighted
users, but the announced copy is debounced (~1s) via a visually-hidden span
so a burst of ten announces once or twice, not ten times.

### 6. Refresh spin via the Web Animations API, not CSS class toggles
A CSS class can't land upright: removing it resets the angle. `RefreshControl`
gets a small `useRefreshSpin(isSpinning)` hook holding an `Animation` on the
icon wrapper:
- **Start**: read the current angle (0 if idle), play a one-turn
  `ease-in` ramp (~450ms, `cubic-bezier(0.5, 0, 0.75, 0)`), then chain an
  infinite linear loop at ~800ms/turn. The ramp's exit velocity is matched
  to the loop's speed so there's no visible hitch.
- **Settle**: on `isSpinning → false`, read the current angle θ from
  `getComputedStyle(...).transform`, cancel the loop, and play
  `rotate(θ) → rotate(ceil(θ/360)·360°)` with `--ease-motion-out`, duration
  proportional to the remaining arc (capped at one standard duration past
  the turn), `fill: 'forwards'`, then reset to 0° on finish.
- **Re-click while settling**: cancel the settle and start the loop from θ
  (skipping the ramp, since it is already moving).
- **Hover nudge**: a CSS `transition: transform var(--motion-standard)` on a
  separate inner wrapper rotating `30deg` (clockwise, the `refresh-cw` icon's direction) on `:hover`/`:focus-visible`,
  disabled while spinning, so it never fights the WAAPI transform on the
  outer wrapper.
- **Reduced motion**: when `matchMedia('(prefers-reduced-motion: reduce)')`
  matches, the hook keeps the existing `animate-spin` class path (which the
  global rule already exempts) and removes it on finish; the nudge's
  transition is already zeroed by the global rule, and the nudge transform
  itself is wrapped in `@media (prefers-reduced-motion: no-preference)`.
*Alternative*: CSS `animation-iteration-count` + `animationiteration` event
to stop at the next boundary. Rejected — it waits up to a full turn at full
speed and then still stops abruptly with no ease-out.

## Risks / Trade-offs

- [Bottom-right toasts can cover a page's bottom-right content, e.g. the
  last board card's buttons or a wizard's "Next"] → toasts are capped at
  three, auto-dismiss, and pause only while hovered; the risk is far smaller
  than covering the global top bar. Revisit if a page has a fixed footer.
- [Existing e2e tests locate toasts or assert top-right placement / the
  `animate-spin` class on the refresh icon] → update `test_live_refresh.py`,
  `test_motion_and_loading.py` and `test_notification_bell.py` in this
  change; assert behaviour (spinning while pending, upright after) via the
  icon's computed transform rather than a class name.
- [Uncommitted `AppTopBar`/`NotificationBell` work in the tree is the base
  for this change] → implement on top of it; do not revert it.
- [WAAPI `getComputedStyle` angle extraction returns a matrix] → derive θ
  with `atan2(b, a)` and track whole turns separately in the hook.
- [A grouped summary discards the individual messages from the toast] →
  every item stays in the bell feed, which the summary opens directly.

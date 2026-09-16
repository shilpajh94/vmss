## Context

`RegistrationStepper.tsx` (10 lines of real markup) renders every step
(circle + label + connector) at fixed px/rem sizes inside a `flex
min-w-max items-center gap-3` row, wrapped in a `w-full overflow-x-auto`
container. `min-w-max` forces the row to never shrink below its natural
(single-line) width, so once the sum of all steps' fixed widths exceeds the
container's available width, the container's own `overflow-x-auto`
silently takes over with no visible scrollbar affordance — see
proposal.md for why this now reproduces at ordinary zoom levels since the
step count became dynamic (5-8+ steps).

## Goals / Non-Goals

**Goals:**
- Every step stays visible/reachable at any viewport width or zoom level,
  with the smallest, lowest-risk change to this component.
- No new JS-side width measurement (`window.innerWidth`, `ResizeObserver`) —
  the current bug exists precisely because sizing is fixed-px rather than
  because it lacks a JS breakpoint; the fix should stay pure-CSS so it
  reflows correctly under zoom (which changes effective CSS-pixel width)
  the same way it would under an actual narrower window.

**Non-Goals:**
- A compact/numbers-only stepper presentation — a valid alternative
  considered below, but not chosen for this pass (see Decisions).
- Changing the stepper's visual design (circle size, colors, connector
  style) beyond what wrapping requires.
- Any change to how the step list itself is computed (`activeSteps`,
  `resolveStepLabel`) — this change is presentation-only.

## Decisions

- **Switch the row to wrap (`flex flex-wrap`), remove `min-w-max` and
  `overflow-x-auto`.** Steps that don't fit on the current row flow onto
  additional rows below it, exactly like a wrapping breadcrumb. This is a
  ~3-class CSS change with no new breakpoint logic, no JS measurement, and
  it degrades identically whether the cause is a narrow window, a small
  device, or zoom — it responds to whatever width the row is actually
  given, at any zoom level, without a specific threshold to get wrong.
  Alternative considered: a compact/numbers-only mode below a width
  breakpoint (option (b) from the investigation). Rejected for this pass —
  it requires either a CSS container-query breakpoint (verify Tailwind
  config supports `@container` here) or a JS width measurement (which Goals
  above rules out), and a numbers-only fallback still needs a way to expose
  each step's label (tooltip/`title` attribute), adding surface area for a
  change whose real requirement is just "don't hide steps." Wrapping meets
  the requirement with less to get wrong, and can be revisited later if a
  single-row layout turns out to matter for its own sake.
  Alternative considered: keep horizontal scroll but add a visible
  affordance (edge fade / chevrons). Rejected as the primary fix — it still
  requires the user to scroll to reach a step, whereas wrapping makes every
  step visible without any interaction, which better satisfies "every step
  stays visible" from the spec. (The proposal keeps a scroll-affordance
  requirement only as a fallback in case a future presentation reintroduces
  horizontal scroll for some other reason — not needed for wrapping itself.)
- **Leave the per-step markup (circle, label, connector) unchanged**, only
  the container's flex-wrap/overflow classes change. The `<div
  className="contents">` wrapper around each button+connector pair means
  `flex-wrap` on the parent already wraps at the right granularity (button
  and its trailing connector move together) without any markup
  restructuring.

## Risks / Trade-offs

- [Risk] A connector line (`w-8 bg-border`) immediately before a wrap point
  will visually "dangle" at the end of a row with nothing after it on that
  row → Mitigation: acceptable, standard behavior for a wrapping
  breadcrumb/stepper; no functional impact (it's decorative), and revisit
  only if it looks wrong once actually viewed in a browser (flagged as a
  manual-verification item in tasks.md, per this repo's established
  precedent for changes made without browser access in this environment).
- [Trade-off] Multi-row stepper takes more vertical space than the current
  single-row-with-hidden-overflow layout on a narrow/zoomed view — accepted
  because the alternative (hidden steps) is the actual bug being fixed;
  vertical space is cheaper to lose than reachability.

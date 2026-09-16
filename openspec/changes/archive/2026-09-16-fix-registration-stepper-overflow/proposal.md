## Why

The visitor-registration wizard's step navigator (`RegistrationStepper.tsx`)
was originally built for a fixed, small step count and lays out every step
(numbered circle, label, connector line) at a fixed pixel/rem width in a
`flex` row with `min-w-max`, wrapped in an `overflow-x-auto` container with
no scroll affordance. Since the branch-scoped form builder made the step
count dynamic (5-8+ steps per branch, per `staff-visitor-registration`'s
existing "stepper... computed from the number of steps actually present,
not a fixed count of six" requirement), the row's total fixed width now
regularly exceeds the available viewport width. The row doesn't wrap or
shrink — it silently falls back to horizontal scroll with no visible
scrollbar affordance (especially with overlay scrollbars), so steps past
the visible edge look "missing" rather than reachable. Because every
dimension is fixed and the container is what shrinks, this reproduces at an
ordinary, unremarkable browser zoom level (not just extreme
zoom-out/zoom-in), making it a realistic everyday failure mode, not an edge
case.

## What Changes

- Replace the stepper's "grow indefinitely + hidden horizontal scroll"
  layout with one that keeps every step visible and reachable regardless of
  step count or viewport width — either by wrapping steps onto additional
  rows below a width threshold, or by switching to a compact
  (numbers-only, tooltip-on-hover label) presentation below that threshold.
  The exact mechanism is a `design.md` decision; the spec requirement is the
  outcome (every step stays visible/reachable), not the technique.
- If any horizontal scrolling is kept as part of that mechanism, it SHALL
  have a visible affordance (e.g. edge fade and/or visible chevrons)
  distinguishing "more steps this way" from "this is the end of the list" —
  never a bare, easy-to-miss scrollbar as the only signal more steps exist.

## Capabilities

### Modified Capabilities
- `staff-visitor-registration`: the existing "progress stepper" requirement
  already establishes the step count is dynamic; this adds the missing
  constraint that every step stays visible/reachable at any viewport width
  or browser zoom level, not just "some", closing the gap that let this
  regress silently once the step count grew past what the original fixed-
  width layout assumed.

## Impact

- `src/presentation/pages/staff-visitor-registration/Components/RegistrationStepper.tsx`
  and its caller `staff-visitor-registration.tsx`.
- No backend changes.

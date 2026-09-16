## 1. Stepper layout fix

- [x] 1.1 In `RegistrationStepper.tsx`, change the row container from
      `flex min-w-max items-center gap-3` (inside a `w-full
      overflow-x-auto` wrapper) to a wrapping layout: `flex flex-wrap
      items-center gap-3` on the row, removing `min-w-max` and the parent's
      `overflow-x-auto` (or replacing it with a plain `w-full` wrapper, if
      one is still needed for spacing).
      Outer wrapper is now `<div className="w-full">`; row is `flex
      flex-wrap items-center gap-x-3 gap-y-2`.
- [x] 1.2 Confirm the per-step `<div className="contents">` grouping
      (button + trailing connector) still wraps as one unit — no markup
      restructuring expected, but verify after the class change.
      Confirmed: `display: contents` removes that wrapper from the box
      tree, so its button/connector children are direct flex items of the
      wrapping row and wrap together at the correct granularity with no
      markup change needed.
- [x] 1.3 Add a small vertical gap between wrapped rows (e.g. `gap-y-2` or
      equivalent) so wrapped rows don't visually touch.
      Added as part of 1.1's class change (`gap-y-2`, kept `gap-x-3` for
      horizontal spacing).

## 2. Verification

- [x] 2.1 `tsc -b` and `oxlint` pass clean.
- [x] 2.2 Manually verify in a browser: with a branch configured to have
      7-8+ active steps, reduce browser zoom until the single-row width
      would have overflowed under the old layout, and confirm every step
      is visible (wrapped onto additional rows) with no hidden/clipped
      step and no reliance on horizontal scrolling.
      Confirmed working by user.
- [x] 2.3 Manually verify: the connector line before a wrap point doesn't
      look broken or confusing; adjust spacing if it does.
      Confirmed working by user.
- [x] 2.4 Manually verify: step selection (clicking a completed step's
      button) still works correctly across wrapped rows.
      Confirmed working by user.

**Note on 2.2-2.4**: no browser tool was available in this implementation
environment (same limitation flagged in `fix-form-builder-layout-and-
refresh-gaps`'s and `improve-listing-ux`'s own tasks.md). The code change
is a minimal, well-understood CSS swap (`flex-wrap` replacing `min-w-max`
+ `overflow-x-auto`, per design.md) and `tsc -b`/`oxlint` pass clean; the
rendered result was then manually confirmed by the user directly.

## Context

- **Steppers.** Staff uses a horizontal `RegistrationStepper`: numbered circles, with 32px `h-px` connector `div`s between them that wrap onto rows. The public wizard uses `StepSidebar` (desktop rail, no connectors) and `StepProgressHeader` (phone; already has `transition-[width]` on its bar). All three take `steps` + `currentStep` and derive `isActive`/`isComplete`. None of them knows which direction the last move went.
- **Step content.** Both pages render a chain of `activeStep?.key === '…' && <Step… />` inside one card. A step switch unmounts one component and mounts another.
- **Motion precedent.** `RouteTransition` is CSS-only: a keyed wrapper with a `.route-transition` keyframe in `src/styles/index.css`, plus a `prefers-reduced-motion` override. No animation library is installed.
- **Avatars.** `utils/initials.ts` (first two words) serves the top bars. `VisitRequestCard` and `VisitorInfoModal` each define a private `initialsFor` (first + last). `VisitorInfoModal` also has a private `Avatar` with photo → initials fallback on `onError`. The three list surfaces render a bare `<span className="size-N rounded-full bg-neutral-subtle" />`.

## Goals / Non-Goals

**Goals:**
- One motion timing (duration and easing) shared by every step indicator and the content slide.
- One `Avatar` component and one initials rule for every person avatar.

**Non-Goals:**
- Animating step *exit*. As with `RouteTransition`, only the entering step animates; keeping the old step mounted for an exit would need cross-fade layering and double-mounted forms.
- Changing which steps are selectable, or any validation behaviour.
- Adding avatars to name-only cells (branches' contact person, departments' head).

## Decisions

### 1. CSS transitions/keyframes, no animation library
The stepper animates with `transition` on existing properties: connector fill via a `scaleX` (horizontal) or `scaleY` (sidebar) inner bar, and circle background/colour, with the number crossfading to a `CheckIcon`. The content slide is a keyframe on a wrapper keyed by step index, the same technique as `RouteTransition`.
- *Alternative: framer-motion / motion.* Adds a dependency for two effects CSS already handles, and would be the first JS animation lib in the app. Rejected.

Shared tokens in `index.css`: `--step-motion-duration: 280ms` and `--step-motion-ease: cubic-bezier(0.2, 0.8, 0.2, 1)`. The stepper, sidebar, progress bar and content keyframe all reference them, so one edit retunes everything and the 300ms spec ceiling is in one place.

### 2. Direction is derived, not passed by callers
A small hook `useStepDirection(currentStep)` keeps the previous index in a ref and returns `'forward' | 'backward' | 'none'`. Both pages call it once and use it for the content slide. The steppers don't need it: connector fill and checkmark state are pure functions of `currentStep`, so CSS transitions animate both directions for free.
- *Alternative: have `goNext`/`goBack`/`goToStep` record direction in the wizard hooks.* That touches two large hooks for derived UI state. Rejected.

### 3. Content slide wrapper
Each page wraps its step chain in `<div key={currentStep} className="step-enter" data-direction={direction}>`. The CSS animates `translateX(24px → 0)` and `opacity 0 → 1` for `forward`, mirrored for `backward`, and nothing for `none` (first render). A small 24px offset reads as movement without layout jank; `overflow-x: clip` on the card stops a transient horizontal scrollbar. Animating only `transform`/`opacity` keeps it on the compositor, and inputs are interactive immediately (spec: no input delay).
- Keying on `currentStep` remounts the step components. That already happens today, since only one step component is mounted at a time, so no state is lost that isn't already lost. Form data lives in the wizard hook.
- Keep the staff page's existing scroll-to-top effect (from `staff-registration-scrollable-form`) as is; it runs on the same step change.

### 4. Initials rule = first two words
`initialsFor` in `utils/initials.ts` becomes the only implementation: split on `/\s+/` after trimming, take the first letters of the first two words, uppercase. It matches the reference badge ("AS"), so the top bars are unchanged. The visit card and visitor modal switch from first+last to this rule (proposal Assumptions). Delete their private copies.

### 5. Shared `Avatar` component
`src/presentation/components/ui/Avatar.tsx`, props: `name`, `photoUrl?`, `size` (`'sm' | 'md'` → `size-7`/`size-9` plus a matching font size), `className?` for overrides. It is lifted from `VisitorInfoModal`'s private `Avatar`, keeping its `onError` → initials fallback. Default style is the reference: `border-[1.5px] border-info bg-info/8 text-info font-display font-bold`. Pass `alt={name}` on the photo; the initials span gets `aria-hidden` because the name is always rendered next to it.
- `VisitorInfoModal` keeps its own tone classes by passing `className`.
- `VisitRequestCard` keeps its hashed tint background via `className`/`style`, since the board relies on tints to tell cards apart.
- The top bars switch to `<Avatar …/>`. Staff bars are unchanged; the admin and reception bars' grey initials adopt the reference style so the signed-in user's badge matches everywhere.
- The photo uses `HostEmployee.avatarUrl` in the employees table. The check-ins and upcoming-visitor summaries have no photo field today, so they show initials only. No API change is needed, and they'll pick up photos automatically if one is added later.

### 6. Reduced motion
One `@media (prefers-reduced-motion: reduce)` block sets the shared duration token to `0ms` and disables `.step-enter`'s animation. This covers stepper transitions, the progress bar, and the content slide without per-component checks.

## Risks / Trade-offs

- [The connector `div`s in the wrapping staff stepper sit at the end of a row; a fill animating at a row break looks odd] → The fill is per-connector and short (32px), so it reads as a tick, not a line crossing rows. Verify at 1024px, where the stepper wraps.
- [Rapid Next/Back clicks restart the keyframe mid-flight] → Keyed remount restarts cleanly from the start state, with no stacking. Acceptable.
- [Switching the visit card's initials rule changes some cards' letters (e.g. "AK" → "AS")] → Intended, for consistency with the reference. Called out in the proposal so reviewers see it.
- [`overflow-x: clip` on the content card could clip a focus ring flush at the edge] → The card has padding (`p-4`+), so rings sit inside it. Check focus on the first input during verification.

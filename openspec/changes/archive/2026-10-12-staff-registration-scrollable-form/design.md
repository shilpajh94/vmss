## Context

`AppShell` already caps the shell at `h-dvh` and makes `<main>` the scroll container. `RouteTransition` stretches its wrapper to `<main>`'s height (`h-full min-h-0 flex-col`), so a page can confine scrolling to one inner region. List pages use this through `PageContentLayout`, which has a fixed `header` and a scrolling `children` region from `lg` up, and falls back to whole-page scrolling below `lg`.

`StaffVisitorRegistrationPage` doesn't opt in. It returns a fragment of four siblings: the workspace header, the stepper, the form card (`flex-1`), and the action bar. Their combined height overflows `<main>`, so everything scrolls together (see proposal.md, Why). The action bar is `sticky bottom-0` below `md` and `md:static` above.

## Goals / Non-Goals

**Goals:**
- Reuse the existing fixed-header/scrolling-body layout rather than add a page-specific flex/overflow arrangement.
- Keep below-`lg` behaviour equivalent to today: one page scroll, with the action bar sticky at the bottom.

**Non-Goals:**
- Changing `AppShell`, `RouteTransition`, or any other page's layout.
- Restyling the header, stepper, form card, or buttons.
- Scrolling to the first invalid field on a failed Next. That's a separate UX improvement; the spec only requires errors to stay reachable.

## Decisions

### 1. Extend `PageContentLayout` with an optional `footer` slot
Add `footer?: ReactNode`, rendered as a `flex-none` sibling after the scrolling region. When `footer` is omitted, the markup is unchanged, so the existing list-page callers aren't affected.

- *Alternative: hand-roll `lg:h-full lg:min-h-0` / `lg:flex-1 lg:overflow-y-auto` in the page.* This duplicates the breakpoint logic `PageContentLayout` already holds and documents. Two copies would drift on the next breakpoint change.
- *Alternative: a new `WizardLayout` component.* Not worth it. The only difference is one optional slot, and keeping a single layout component means one place defines "where the page scrolls".

### 2. Page composition
`header` = `RegistrationWorkspaceHeader` + `RegistrationStepper`. `children` = the existing form card. `footer` = the existing action bar. The form card keeps its own border, rounding, and padding inside the scroll region, so the scrollbar sits on the region's edge, not inside the card. The scroll region also gets the project's `scrollbar-thin` utility, used by the form-builder pages.

### 3. Action bar classes
The bar already lives outside the scroll region from `lg` up, so it no longer needs to be sticky there. Below `lg` the page scrolls as one and the bar must stay at the bottom (spec scenario "Below desktop width the page scrolls as one"). So `md:static md:mx-0 md:px-0 md:pb-0` becomes `lg:` variants. This also extends the sticky behaviour to the `md`–`lg` tablet range, which matches the spec and is an improvement there, since tablets currently scroll the buttons away too.

### 4. Reset scroll on step change
Attach a ref to the scroll region (`PageContentLayout` forwards a `bodyRef` or accepts `ref` on the body) and set `scrollTop = 0` in an effect keyed on `currentStep`. Below `lg` the scroller is `<main>`, not the body, so in that case the effect scrolls the body element's top into view instead (`scrollIntoView({ block: 'start' })` on the layout root). Both are cheap and run only on step change.

- *Alternative: key the scroll region on `currentStep` to remount it.* That would remount every step component and lose local UI state (open dropdowns, previews) for no reason.

## Risks / Trade-offs

- [The header plus a wrapped stepper are tall at `lg` widths near 1024px, which leaves a short form region] → The stepper already wraps rather than overflowing. At 1024×768 the form region is still roughly 300px. Verify via the screenshot script at 1024 and 1366 widths, and if too cramped, raise the breakpoint for this page only through a prop. Don't change the shared default.
- [Spacing shift: the page goes from a fragment spaced by `RouteTransition`'s `gap-page-section` to one root spaced by `PageContentLayout`'s `gap-4 md:gap-6`] → Compare before/after screenshots; adjust only if the visual gap changes noticeably.
- [Open dropdown/date-picker popovers inside a scroll container could clip] → Native `<select>` isn't affected. Check any custom popovers in the dynamic-field components during verification.

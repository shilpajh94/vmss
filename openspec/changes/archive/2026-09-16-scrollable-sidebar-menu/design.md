## Context

See `proposal.md` - Why for motivation. Both sidebar components share the same structure today:

```tsx
<aside className="flex w-[280px] shrink-0 flex-col gap-4 self-stretch bg-primary p-6">
  <button>...logo...</button>
  <nav className="flex flex-1 flex-col gap-1.5">
    {NAV_ITEMS.map(...)}
  </nav>
  <div>...footer (version badge / help button)...</div>
</aside>
```
(`DashboardSidebar` additionally wraps its footer in `flex flex-1 flex-col justify-end` to pin it to the bottom via leftover flex space — see Decision below for why that trick doesn't survive this change.)

`AppShell` renders this `<aside>` inside a `flex h-screen ... overflow-hidden` row, with `self-stretch` sizing it to the shell's full height. Nothing inside the `<aside>` currently has its own `overflow-y-auto`, so when the three children (`header + nav + footer`) sum to more than the available height, the outer shell's `overflow-hidden` simply clips the excess — there is no scrollbar and no way to reach the clipped items.

## Goals / Non-Goals

**Goals:**
- The nav item list scrolls internally when it doesn't fit, without needing an `AppShell` change.
- The logo header and footer content stay visible/pinned regardless of nav list length.

**Non-Goals:**
- No visual redesign of the sidebar (colors, spacing, item styling unchanged).
- No change to `AppShell`, `AdminTopBar`, or the main content scrolling behavior — this is scoped to the two sidebar components only.

## Decisions

**Split the `<aside>` into three flex rows: fixed header, scrolling nav, fixed footer.**
```tsx
<aside className="flex w-[280px] shrink-0 flex-col gap-4 self-stretch bg-primary p-6">
  <button className="shrink-0">...logo...</button>
  <nav className="flex flex-1 flex-col gap-1.5 overflow-y-auto min-h-0">
    {NAV_ITEMS.map(...)}
  </nav>
  <div className="shrink-0">...footer...</div>
</aside>
```
The `min-h-0` on `<nav>` is required, not optional: a flex child's default `min-height` is `auto`, which means it won't shrink below its content's intrinsic height — so `overflow-y-auto` silently never triggers without it (the classic flexbox-scrolling gotcha). `shrink-0` on the header/footer prevents them from being compressed to make room for a growing nav list; they keep their natural size and the nav list absorbs all the available/overflowing space instead.

*Alternative considered*: make the whole `<aside>` scroll as one unit (a single `overflow-y-auto` on the `<aside>` itself, no structural split). Rejected — it would scroll the logo and footer out of view along with the nav items, which contradicts "the sidebar and top navigation bar remain fixed" (the existing, unchanged part of this same requirement) and breaks `DashboardSidebar`'s footer, which is specifically positioned at the bottom via `justify-end`; that positioning only works while there's leftover flex space; once scrolling, it would move into normal flow instead of double-fixed-anchoring, which is a worse behavior change than just keeping the 3-row split.

**Apply identically to both `AdminSidebar` and `DashboardSidebar`.**
They're structurally identical for this purpose (logo header, `<nav>` of items, footer); the same 3-row split applies to both with no component-specific variation needed.

## Risks / Trade-offs

- **[Risk] `min-h-0` is a non-obvious, easy-to-omit fix** → Mitigation: called out explicitly in tasks.md so it isn't dropped during implementation; this is the one line that actually makes the scroll work, everything else is cosmetic.
- **[Risk] Visual regression: scrollbar appearing inside a colored (`bg-primary`) sidebar could look different from the app's default scrollbar styling** → Mitigation: low risk, no custom scrollbar styling exists elsewhere in the app either (browser default is used for `<main>` already); accept the default appearance, revisit only if design feedback flags it.

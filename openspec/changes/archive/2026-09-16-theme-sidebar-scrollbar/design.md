## Context

See `proposal.md` - Why for motivation (screenshot showed the native browser scrollbar — light, bordered, with arrow buttons — rendered against the sidebar's dark `bg-primary` background after `scrollable-sidebar-menu` made the nav list scroll).

Relevant current state:
- `AdminSidebar.tsx` and `DashboardSidebar.tsx` both scroll their `<nav>` element (`overflow-y-auto`, from `scrollable-sidebar-menu`) — no scrollbar styling exists anywhere in the codebase today (`grep -rn scrollbar src/` returns nothing), so this is a net-new addition, not a conflict with an existing rule.
- The sidebar's own palette is a dark navy (`bg-primary` = `#0F172A`) with hardcoded slate accents used nearby (`border-[#334155]`, `text-text-faint` = `#94a3b8`, `hover:bg-white/5`) — there's no single semantic "sidebar scrollbar" token in `theme.css` to reuse as-is, so this introduces small new color values tuned to sit well against `#0F172A` without a formal token (consistent with how the sidebar already uses a few hardcoded slate hex values alongside the semantic tokens, e.g. `border-[#334155]`).
- The main content area's scrollbar (light background, `<main>` in `AppShell`) is out of scope — it already looks fine against a white background with the OS default, and the proposal explicitly scopes this to the sidebar only.

## Goals / Non-Goals

**Goals:**
- Sidebar nav list scrollbar visually fits the dark sidebar (thin, flat, no arrow buttons, subtle thumb color) in both Chromium/Safari (`::-webkit-scrollbar`) and Firefox (`scrollbar-width`/`scrollbar-color`).
- No change to the scroll mechanics themselves (`flex-1 min-h-0 overflow-y-auto` from `scrollable-sidebar-menu` is untouched).

**Non-Goals:**
- Not touching the main content area's scrollbar, or any other scrollable region in the app.
- Not introducing a general-purpose "themed scrollbar" utility class for reuse elsewhere — scoped narrowly to the sidebar nav list for now; broader scrollbar theming is a separate decision if it comes up later.

## Decisions

**A single `.sidebar-nav-scroll` class in `src/styles/index.css`, applied to both sidebars' `<nav>` elements.**
```css
.sidebar-nav-scroll {
  scrollbar-width: thin;
  scrollbar-color: rgba(255, 255, 255, 0.18) transparent;
}

.sidebar-nav-scroll::-webkit-scrollbar {
  width: 6px;
}

.sidebar-nav-scroll::-webkit-scrollbar-track {
  background: transparent;
}

.sidebar-nav-scroll::-webkit-scrollbar-thumb {
  background-color: rgba(255, 255, 255, 0.18);
  border-radius: 9999px;
}

.sidebar-nav-scroll::-webkit-scrollbar-thumb:hover {
  background-color: rgba(255, 255, 255, 0.32);
}
```
Applied as `<nav className="flex min-h-0 flex-1 flex-col gap-1.5 overflow-y-auto sidebar-nav-scroll">` (and the `DashboardSidebar` equivalent).

*Why a plain CSS class instead of Tailwind utilities*: Tailwind v4 (already in use here, per `@import "tailwindcss"` in `index.css`) has no built-in utilities for `::-webkit-scrollbar-*` pseudo-elements or `scrollbar-color`; these require a real CSS rule with pseudo-element selectors, which is most simply expressed as a small hand-written class alongside the project's other hand-written rules in `index.css` (e.g. `.route-transition` from `fix-app-shell-ux-polish`).

*Why `rgba(255,255,255,0.18)` instead of an existing token*: it needs to read as a subtle, translucent overlay on `#0F172A` — similar in spirit to the sidebar's existing `hover:bg-white/5` treatment on nav items, just slightly more opaque so the thumb stays visible at rest (not just on hover, unlike the nav-item hover state). No existing semantic token targets "translucent white on dark," so a literal rgba value is used, matching the sidebar's existing pattern of a few hardcoded values alongside semantic tokens (`border-[#334155]`, `bg-white/5`).

*Alternative considered*: a fully custom scroll thumb via a JS scrollbar library (e.g., `simplebar`, `overlayscrollbars`). Rejected — adds a dependency and JS overhead for a purely cosmetic fix that native CSS scrollbar styling already covers in every browser this app needs to support; consistent with `fix-app-shell-ux-polish`'s precedent of preferring CSS-only solutions over new dependencies for visual polish.

## Risks / Trade-offs

- **[Risk] `::-webkit-scrollbar` styling has no effect in Firefox, and `scrollbar-width`/`scrollbar-color` has no effect in Chromium/Safari** → Mitigation: both rules are included together (as shown above) specifically so each engine picks up its own supported mechanism; this is the standard cross-browser pattern for scrollbar theming, not a gap.
- **[Risk] Very old browser versions ignore both mechanisms and fall back to the native scrollbar** → Mitigation: acceptable — the native scrollbar was the pre-existing (and only) behavior for those browsers before this change too, so this is a strict improvement with no regression path.

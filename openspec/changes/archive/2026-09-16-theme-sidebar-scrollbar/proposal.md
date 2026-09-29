## Why

`scrollable-sidebar-menu` made the sidebar's nav list scroll internally instead of clipping, but it relies on the browser's default scrollbar. Against the sidebar's dark navy background (`bg-primary`, `#0F172A`) that renders as a bulky, light-gray, OS-chrome-style scrollbar with up/down arrow buttons — visually out of place next to the rest of the app's flat, minimal design language, and reported directly from a screenshot as "looks like the old one." The scroll behavior itself is correct; only its appearance needs to match the theme.

## What Changes

- Style the sidebar nav list's scrollbar (thumb + track) to fit the dark sidebar theme: a thin, flat, semi-transparent light thumb (visible against `bg-primary` without competing with active/hover item colors) on a transparent track, with no visible arrow buttons — replacing the native OS/browser default scrollbar.
- Cross-browser: `scrollbar-width`/`scrollbar-color` for Firefox, `::-webkit-scrollbar*` pseudo-elements for Chromium/Safari, applied only to the sidebar's nav list (not globally, so the light-background main content area keeps the default scrollbar it already has).
- Applies to both `AdminSidebar` and `DashboardSidebar`'s nav lists — the same two components `scrollable-sidebar-menu` touched.

## Capabilities

### Modified Capabilities
- `app-shell`: extend the "Sidebar and top navigation remain fixed while content scrolls independently" requirement (already covers the sidebar's nav list scrolling internally) with the additional constraint that the scrollbar's appearance is themed to fit the dark sidebar, not the browser default.

## Impact

- **Affected code**: `src/styles/index.css` (new scrollbar-styling rule, scoped to a class applied to the sidebar's `<nav>`), `src/presentation/components/AdminSidebar.tsx` and `src/presentation/components/DashboardSidebar.tsx` (add that class to their `<nav>` element — no structural change, `scrollable-sidebar-menu`'s flex/overflow setup is untouched).
- **Visual only** — no behavior, prop, or data change; purely a CSS styling addition on top of the already-working scroll mechanics.
- **No backend impact** — frontend-only (VMMS_WEB).

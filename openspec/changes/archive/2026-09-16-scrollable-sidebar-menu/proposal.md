## Why

The shared `AppShell` layout (introduced in `fix-app-shell-ux-polish`) fixes the sidebar in place via `h-screen`/`overflow-hidden` so it no longer scrolls away with the page — but it has no internal scroll of its own. `AdminSidebar`/`DashboardSidebar` render a fixed-height `<aside>` with a logo header, the nav item list, and a footer, none of which has `overflow-y-auto`. When the nav list is longer than the viewport (a real case for `AdminSidebar`, which already has 14 nav items and will gain more as new admin features land), the excess items are simply clipped by the shell's `overflow-hidden` and become unreachable — there's no way to scroll down to them. This was reported directly from real usage.

## What Changes

- Make the sidebar's nav item list scroll internally (`overflow-y-auto`) when it's taller than the space available, while the logo header at the top and the footer (version badge / help button) stay pinned in place — mirroring the same fixed-chrome/scrolling-content pattern `AppShell` already applies to the page's main content and top bar.
- Applies to both `AdminSidebar` and `DashboardSidebar`, the only two sidebar components in the app.

## Capabilities

### Modified Capabilities
- `app-shell`: extend the existing "Sidebar and top navigation remain fixed while content scrolls independently" requirement so it also covers the sidebar's own nav list scrolling internally when it doesn't fit the viewport, instead of being clipped.

## Impact

- **Affected code**: `src/presentation/components/AdminSidebar.tsx`, `src/presentation/components/DashboardSidebar.tsx` — internal layout only (a `flex flex-col` region split into a fixed header, a scrollable nav list, and a fixed footer). No prop or behavior change visible to callers (`AppShell`, pages).
- **No change to `AppShell` itself** — the sidebar already renders inside a `self-stretch` slot with the correct available height; this change only makes the sidebar's own content handle overflow instead of the shell.
- **No backend impact** — frontend-only (VMMS_WEB).

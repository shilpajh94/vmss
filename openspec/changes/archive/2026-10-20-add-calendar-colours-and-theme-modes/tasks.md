Web-only change; no API work. Never run prettier in VMMS_WEB.

## 1. Tokens and the dark palette

- [x] 1.1 In `src/styles/theme.css`:
  - add `--color-on-primary`, `--color-on-accent` (both `#ffffff`) and
    `--color-text-secondary` (`#475569`) to `@theme`;
  - add a `:root[data-theme="dark"]` block with every dark value from the
    design-theme spec, plus `color-scheme: dark`;
  - set `color-scheme: light` on `:root`;
  - add the chart series dark values (design.md D7).
- [x] 1.2 Add `@custom-variant dark (&:where([data-theme=dark], [data-theme=dark] *));`
  to `theme.css` (D1).
- [x] 1.3 Check that the light theme is unchanged: compare computed token
  values on `/admin/dashboard` against a pre-change snapshot (light).

## 2. Mode state, pre-paint script and scoping

- [x] 2.1 `presentation/context/theme-mode-context.tsx`:
  - `ThemeModeProvider` and `useThemeMode()` exposing `mode`,
    `resolved` and `setMode`;
  - `localStorage['vmss.themeMode']` via `use-stored-state`, falling back
    to `'system'`;
  - a `matchMedia('(prefers-color-scheme: dark)')` subscription;
  - cross-tab sync through the `storage` event (D4).
- [x] 2.2 `useApplyTheme(force?: 'light')` sets or removes `data-theme` on
  `<html>` and updates `<meta name="theme-color">`. Call it from
  `AdminLayout` and `StaffLayout`, and call `useApplyTheme('light')` from
  `PublicLayout`. Wrap the app in `ThemeModeProvider` in `App.tsx`.
- [x] 2.3 Add the inline pre-paint script to `index.html` (D5). It applies
  dark only on `/admin/`, `/staff/` and `/reception/` paths that aren't
  `/admin/login`, `/staff/login` or `/staff/sso…`. Add cross-reference
  comments in the script and in `useApplyTheme`.

## 3. Hard-coded colours → tokens

- [x] 3.1 Audit every `text-white`. Convert the ones on solid accent,
  status or primary fills to `text-on-accent` / `text-on-primary`; leave
  the ones on sidebar navy or images alone (D2). Record the remaining
  `text-white` count with its justification.
- [x] 3.2 Convert the about 45 arbitrary hex classes and about 8
  `bg-white`/`bg-black` outside the sidebars to tokens, using D3's
  mapping. Mark the sidebar and `SidebarHeader` hexes with `theme-fixed`.
- [x] 3.3 Add `scripts/check-theme-colors.mjs` and chain it into
  `npm run lint`. It fails on an arbitrary hex colour class or on
  `bg-white`/`bg-black` under `src/presentation` without `theme-fixed`.

## 4. Theme control

- [x] 4.1 Add sun, moon and monitor glyphs to `components/icons.tsx` if
  they're missing.
- [x] 4.2 `components/ThemeModeMenu.tsx`:
  - an icon button showing the current mode;
  - a `role="menu"` popover of `menuitemradio` items (Light, Dark,
    System) with `aria-checked`;
  - arrow keys move between items, Enter/Space selects, Escape and an
    outside click close it;
  - `usePresence` motion (D6).
- [x] 4.3 Place it in `AppTopBar` between refresh and the bell, kept at
  phone width as an icon only. Check that the 360px top bar is still one
  row.

## 5. Charts and calendar colours

- [x] 5.1 `chart-theme.ts`: include `resolved` from `useThemeMode()` in
  `useChartTheme`'s memo dependencies (D7). Run the CVD/contrast check on
  the dark series values and record the result.
- [x] 5.2 `pages/calendar/calendar-status.ts`: add `fillClass` (a 15% tint,
  25% in dark, plus status text) per status and a `busyTint(total)` helper
  (0 / 1–4 / 5–14 / ≥15) (D8).
- [x] 5.3 `CalendarEventChip`:
  - compact, block and detail chips are drawn filled with `fillClass` and
    a 3px category left accent;
  - the status stays in the visible label (block/detail) and the
    `aria-label`.
- [x] 5.4 `MonthGrid`: the day count badge (desktop and phone) uses
  `busyTint`. `CalendarToolbar` filter chips use `fillClass` when on.
- [x] 5.5 Contrast table: compute text-vs-fill (composited over `surface`)
  for the six statuses in light and dark, all ≥4.5:1. Record it here and
  adjust the tint or text token if any fall short.

## 6. Verification

- [x] 6.1 Run `tsc -b`, `npm run lint` (including the new theme check) and
  `npm run build`.
- [x] 6.2 Add `e2e/test_theme_mode.py`:
  - the control appears on a staff page and an admin page;
  - choosing Dark sets `data-theme="dark"`, and the setting survives a
    reload;
  - System follows an emulated `prefers-color-scheme` (Playwright
    `color_scheme`), including a live change;
  - with Dark stored, `/staff/login` and the visitor portal have no
    `data-theme`;
  - storage throwing falls back to System;
  - keyboard operation of the menu;
  - the 360px top bar is one row.
- [x] 6.3 Extend `e2e/test_staff_calendar.py`:
  - month events carry status fills (computed background is not the
    surface colour);
  - the busy-day tint steps up;
  - filter chips match the event fills.
- [x] 6.4 Dark screenshot sweep: open every staff and admin route in dark
  at 1440 and 390, and check that no element has a computed background of
  `#ffffff`. Review the screenshots by hand, including modals, dropdowns,
  toasts and charts.
- [x] 6.5 Light regression: compare light screenshots of the dashboard,
  calendar, invitations board and one admin list against the pre-change
  ones. The only expected differences are the calendar's new fills.
- [x] 6.6 Re-run the existing e2e suites (`test_live_dashboards.py`,
  `test_auth_and_dashboards.py`, `test_staff_calendar.py`). Never run them
  alongside the API's pytest.

## Implementation notes

**Results**
- Light tokens: all 16 computed values are identical to the pre-change
  snapshot.
- Light screenshots: the baseline for the two dashboards and the
  invitations board caught skeleton states, so their pixel diff is
  load-timing. The loaded pages were reviewed by eye. The only visual
  changes are the calendar fills and the new top-bar theme button.
- Dark sweep: 31 routes at 1440 and 390, plus a modal and the open theme
  menu. No element keeps a white background (switch knobs excepted, by
  design), and every page applies dark.
- e2e: `test_theme_mode.py` 9/9; `test_staff_calendar.py` 19/19.
  Dashboards + auth + calendar + theme: 59 passed, 2 known xfail.

**Deviations from the plan**
- **Sidebar.** Fixed `sidebar-*` tokens replace the planned `theme-fixed`
  hexes. The sidebars also used theme tokens (`bg-primary`,
  `text-text-faint`, `bg-admin-accent`), which flip in dark, so hex
  markers alone wouldn't have kept them navy.
- **New tokens.** Added fixed `knob` (switch knobs, white) and `ink` (dark
  initials on the board's pastel avatar tints). Added `border-strong` and
  `surface-muted` for the `#cbd5e1`/`#f8fafc` hexes so light stays
  identical; they are added to the design-theme spec table.
- **Floor access badges.** These now use a tint, a dot and body text. A
  status-coloured label on its own tint was unreadable for amber, so the
  light-mode label colour changes from coloured to dark.
- **`theme-color` meta.** Left at `#0F172A`. It already equals the navy
  used by the sidebar and the dark surface, so no per-theme update is
  needed.
- **Calendar text (design.md D8, revised).** Event text is body text on
  the status fill, not status-coloured, because that measured below 4.5:1.
  The strong busy step is a 45% tint rather than solid. The design records
  the contrast table.
- **Chart re-read.** `useChartTheme` re-reads tokens in a passive effect,
  not a memo. During render, `<html>` doesn't yet carry the new theme.


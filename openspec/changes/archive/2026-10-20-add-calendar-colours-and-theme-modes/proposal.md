## Why

The calendar is hard to scan. Events are plain white rows with only a 6px
status dot and a thin category border, so a busy day reads as a wall of
grey text. You can't see at a glance which visitors are pending, expected,
inside or missed. Staff also work at reception desks and security posts
for long shifts, often in dim rooms, and the portal has only a bright
light theme. They want to pick Light, Dark, or follow their device
(System).

## What Changes

- **Calendar events are filled with their status colour.**
  - Every event chip (month, week and day views) gets a tinted background
    and matching text in its status colour:
    - Pending: info blue
    - Expected: success green
    - Inside: cyan
    - Visited: neutral grey
    - Missed: amber
    - Denied: red
  - The visitor-category colour stays as a stronger left accent.
  - The status is still also given in text (the label in week/day views,
    and the accessible name everywhere).
  - In month view, a day's visit count gets a busier tint as the count
    grows, so heavy days stand out.
  - The status filter chips use the same fills, so they double as the
    legend.
- **Theme mode switching: Light / Dark / System.**
  - A theme control in the top bar of every staff and admin page (admin,
    reception, security, host).
  - System follows the device's `prefers-color-scheme` and updates live
    when the device switches.
  - The choice is remembered in this browser. The default is System.
  - There is no flash of the wrong theme on load or reload.
- **A dark palette for the design tokens.**
  - Surface, border, text and the status/accent tokens get dark-theme
    values with readable contrast.
  - The light theme is unchanged.
  - The remaining hard-coded colours in staff and admin components
    (about 45 hex classes and about 8 `bg-white`) move to tokens so they
    follow the theme.
  - The dashboard charts re-read their colours when the theme changes.
- **Public pages stay light.**
  - The visitor portal, request wizard, tracking, OTP and the staff/admin
    login pages always render in the light theme, whatever the stored
    choice.

## Capabilities

### New Capabilities
- `theme-mode`: choosing Light / Dark / System for the signed-in staff and
  admin portals. Covers the control, persistence in the browser, following
  the device, applying the theme without a flash, and which pages it
  applies to.

### Modified Capabilities
- `design-theme`: the semantic colour tokens gain a dark-theme value set,
  and the light values stay exactly as specified.
- `staff-calendar`: "Events show schedule, status and visitor at a glance"
  now requires status-filled events, a busy-day tint and a status legend.
- `app-shell`: "Top bar compacts on small screens" keeps the theme control
  on phones.

## Impact

- **VMMS_WEB only.** No API change, because the choice lives in the
  browser's `localStorage`.
- **Styles:** a `:root[data-theme="dark"]` token block and a Tailwind
  `dark` custom variant in `styles/theme.css`.
- **New code:**
  - an inline pre-paint script in `index.html`;
  - `ThemeModeProvider`/`useThemeMode`;
  - a `ThemeModeMenu` in `AppTopBar`.
- **Changed code:**
  - the layouts (`AdminLayout`/`StaffLayout` apply the theme,
    `PublicLayout` forces light);
  - `chart-theme.ts` (re-resolve on change);
  - the calendar components and `calendar-status.ts`;
  - about 30 components with hard-coded colours.
- **Dependencies:** none added.

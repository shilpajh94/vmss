## Why

Three problems staff hit with the new calendar and theme modes:

- **The week view can't hold a busy day.** Every visit is rendered into
  hour rows, so a Monday with 181 visits turns the whole page into an
  endless scroll. The other six days become a long empty band, and the
  toolbar scrolls out of reach.
- **Switching theme looks laggy and jumpy.**
  - About 50 components fade their colours at different speeds (100ms and
    180ms transitions), so the page recolours in visible waves.
  - The dashboard charts recolour one frame after everything else.
  - The menu's closing animation plays on top of all that.
- **Two admin pages are cut off on phones.** A device sweep (320–1920px,
  31 routes) found content wider than the screen on
  `/admin/organisation-configs` and `/admin/audit-trail` at 320–414px,
  clipped and unreachable. Nothing guards against new cases.

This change has a companion change of the same name in VMSS_API. That one
adds the per-day paging the week columns load from. Deploy it first.

## What Changes

- **Week view becomes seven independently scrolling day columns.**
  - The columns sit in a board sized to the screen, so the page itself no
    longer grows.
  - Each column shows its day's visits under sticky hour headings
    ("Any time", "10:00 AM"…).
  - Each column shows at least 10 visits at first, then lazily loads the
    next 10 as the user scrolls near its end, from the API's per-day
    pages.
  - The column header keeps the day's exact total. A "Showing 30 of 181"
    footer shows progress.
  - On phones and tablets the columns snap-scroll sideways (one, two or
    three per screen), each still scrolling on its own.
- **Day view uses the same paged loading.** The list is no longer capped
  at 1,000 per request.
- **Month view asks for only what it shows:** 3 visits per day, with exact
  totals.
- **The "not every visit is listed" banner goes away.** With per-day paging
  no view truncates.
- **Theme switching is instant and clean.**
  - The theme is put on the page before React re-renders, so every
    surface, including the charts, changes in one frame.
  - Colour transitions are suspended during the switch.
  - Where the browser supports it, a short (150ms) cross-fade plays. It is
    skipped under reduced motion.
  - The menu closes without overlapping animation.
- **Responsive across devices.**
  - Fix the overflow on `/admin/organisation-configs` and
    `/admin/audit-trail`.
  - Add an automated device-matrix check (320, 360, 390, 414, 768, 820,
    1024, 1280, 1440, 1920) over every staff and admin route in both
    themes. It fails if content overflows the page or the main area, or
    if the top bar wraps.

## Capabilities

### New Capabilities
<!-- None -->

### Modified Capabilities
- `staff-calendar`:
  - Week view becomes scrolling day columns with lazy loading.
  - Day view loads in pages.
  - The truncation banner is removed.
  - The small-screen behaviour of the week board changes.
- `theme-mode`: adds a requirement that switching repaints in one step,
  with no staggered fades, and with an optional short cross-fade that
  respects reduced motion.
- `app-shell`: adds a requirement that every staff and admin page fits the
  supported device widths without clipped or overflowing content.

## Impact

- **Calendar:**
  - `pages/calendar/components/WeekView.tsx` is rewritten as `WeekBoard`
    plus `DayColumn`.
  - `DayAgenda` gets paged loading.
  - New `use-day-pages` hook.
  - `use-calendar-feed` sends `perDayLimit`.
- **Data layer:** the repository, use case and endpoint gain the day-page
  call and the `perDayLimit` param.
- **Theme:**
  - `theme-mode-context.tsx` gains synchronous apply plus a switching
    guard.
  - `index.css` gains the transition-suppression rule and the
    view-transition styles.
  - `ThemeModeMenu` closes without overlap.
  - `chart-theme.ts` reads in render again.
- **Responsive:** fixes in the organisation-configs and audit-trail pages,
  plus a new `e2e/test_responsive_matrix.py`.
- **Dependencies:** none added. Uses `IntersectionObserver` and the View
  Transitions API with feature detection.

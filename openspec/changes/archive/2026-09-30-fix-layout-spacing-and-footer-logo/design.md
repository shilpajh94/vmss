## Context

The findings come from Playwright screenshots at 375, 768 and 1440px of 18
routes (`assets/shoot.py`). None of the 54 screenshots scrolls
horizontally. The defects are spacing and alignment, and they're identical
across widths, which points to shared components rather than
breakpoint-specific classes.

- `RouteTransition` renders
  `<div key className="route-transition flex h-full min-h-0 flex-col">`.
  `AppShell`'s `<main>` has `gap-page-section`, but `<main>`'s only child
  is this wrapper. 9 pages return `<>…</>`, so their sections become direct
  children of the gap-less wrapper.
- `BrandLogo` renders `<img class="block w-auto shrink-0 h-7">`. In the
  `PortalFooter`'s `flex flex-col` column, `align-self: stretch` sets the
  used width to the column width (400px), which distorts the logo. Rows
  that use `items-center` are unaffected, which is why the sidebars and
  headers look right.
- `RegistrationWorkspaceHeader` uses `px-4 py-4 md:px-10 md:py-5` inside
  `<main class="p-page-content">`.
- `responsive-table.ts` pins the last column with `sticky right-0`, while
  cells stay `whitespace-nowrap`. On a phone the table overflows, and the
  pinned column overlays whatever scrolls under it, which is the status.

## Goals / Non-Goals

**Goals:** fix these in shared components where the cause is shared, and
make the screenshot check repeatable, so "looks right on all devices" is
verifiable rather than asserted.

**Non-Goals:** a visual redesign, or fixing the API-side `signature_pad`
500 that leaves the step lists empty in the dev data.

## Decisions

### 1. The gap lives on `RouteTransition`
Add `gap-page-section` to the wrapper. Single-root pages (every
`PageContentLayout` page, and the form pages that return one `div`) have
one child, so the gap does nothing for them. That makes this safe
globally. Pages that added `mt-*` or `pt-*` to fake the missing gap are
found in the screenshot pass and cleaned up. Candidates are the
admin-dashboard KPI row and the staff dashboard search bar.

*Alternative:* wrap each fragment page in `<div class="flex flex-col
gap-page-section">`. That's 9 edits, and the next new page would regress.
Rejected.

### 2. `BrandLogo` can't stretch
`className = 'block h-8 w-auto max-w-fit shrink-0 object-contain
object-left'`, keeping the caller's height class. `max-w-fit` caps the
used width at the image's fit-content width, which for a replaced element
is `height × ratio`, so stretch alignment can't widen it. `object-contain`
is belt-and-braces if some layout still forces a box. The footer also
gets `self-start` to make the intent explicit.

### 3. Tables: wrap the identifier, protect the status
`RESPONSIVE_TABLE_CLASS` gains:
- `max-md:[&_tbody_td:first-child]:whitespace-normal` and
  `max-md:[&_tbody_td:first-child]:min-w-[8rem]`;
- `[&_tbody_tr>*:last-child]:shadow-[-8px_0_8px_-8px_rgba(15,23,42,0.15)]`;
- `[&_tr>*:last-child]:border-l [&_tr>*:last-child]:border-border-subtle`.

The status cells already carry `whitespace-nowrap`. The `th` header text
for status stays on one line.

### 4. Top bar on phone
`AdminTopBar` already receives `breadcrumb`. Below `md` it shows only the
active item. Only three admin pages (branch create, role create, role
permissions) actually publish a breadcrumb; the rest publish just a
description. So when there's no breadcrumb, the phone title comes from
`AdminSidebar.adminNavLabelFor(pathname)`: the nav label of the route's
active item ("Branches"), which is "Dashboard" for the dashboard and any
unmatched route. From `md` the "Organization Admin" plus description
header is unchanged.

The avatar reuses the `initialsFor(name)` helper from `WorkspaceHeader`,
moved to `presentation/utils/initials.ts` and shared by both.

### 5. Repeatable screenshot check
`scripts/screenshot-pages.py` takes `assets/shoot.py`, generalised:
- the base URL and credentials come from env vars;
- output goes to `./screenshots.local/`, already gitignored by the
  existing `*.local` rule, so `.gitignore` isn't touched;
- it exits non-zero if any route has `scrollWidth > innerWidth`.

Run it with:

    docker run --rm --network host -v "$PWD":/w -w /w \
      mcr.microsoft.com/playwright/python:v1.55.0-noble \
      bash -c "pip install -q playwright==1.55.0 && python scripts/screenshot-pages.py"

It's exposed as `npm run screenshots` and documented in the script's
docstring (the repo has no README). It isn't wired into CI:
the image is about 2 GB, and CI has no seeded API.

## Risks / Trade-offs

- [The global gap double-spaces a page that already added its own margin]
  → The screenshot pass after the change catches it, and those margins are
  removed.
- [`max-w-fit` on `img` in old Safari] → It's supported since Safari 11
  (`max-width: fit-content` with the `-webkit-` prefix handled by
  Tailwind v4). Acceptable.

## Migration Plan

Frontend-only. Ship it, then re-run the screenshot script and compare
against `assets/before-*.png`. Rollback is a revert.

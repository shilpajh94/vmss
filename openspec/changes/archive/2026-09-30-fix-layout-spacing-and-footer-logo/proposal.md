## Why

A review of the portal at phone (375px), tablet (768px) and desktop
(1440px) found layout defects on several pages, the same at every width.
The screenshots are in `assets/before-*.png` and were produced by
`assets/shoot.py` in the Playwright container.

1. **The footer logo is stretched** into a flattened, oversized wordmark on
   the landing, request and track pages (`before-footer-logo-desktop.png`).
   `<BrandLogo>` sits in a `flex-col` column whose default `align-items:
   stretch` widens the `<img>` to the full column width.
2. **Page sections touch with no spacing:**
   - on the admin dashboard, the greeting card touches the KPI cards;
   - on Visits, the header touches the search/filter row, which touches
     the status columns;
   - on Create Branch, the title touches the form card.

   (`before-visits-no-gaps-desktop.png`,
   `before-dashboard-no-gaps-phone.png`, `before-branch-create-desktop.png`.)
   The cause is that `RouteTransition` wraps every page in one `div` with no
   `gap`. Any page that returns a fragment loses `<main>`'s
   `gap-page-section`, because the gap then applies to the single wrapper
   instead of the page's sections.
3. **The Register Visitor header is double-padded.** It adds its own
   `px-4 md:px-10` inside the already padded content area, so the title
   sits 40px further in than the card below it
   (`before-register-visitor-desktop.png`).
4. **Create Branch's "Operational Status" row** puts the toggle at the far
   edge of a 240px box, with the status text on a separate line, and
   doesn't line up with the "Internal Administration Notes" field beside
   it.
5. **The Branches table on a phone** clips the Status pill under the pinned
   Actions column: the "ST" header and the pill are cut off
   (`before-branches-table-phone.png`). The name column won't wrap, so the
   table is always wider than the screen.
6. **The phone top bar** shows a truncated "Organizat…" and an empty grey
   avatar circle.

## What Changes

- `RouteTransition` applies `gap-page-section` to its wrapper, which fixes
  every fragment-rooted page at once. Pages that already manage their own
  gaps are unaffected, since they return a single root.
- `<BrandLogo>` never stretches (`max-w-fit` plus `object-contain`,
  aspect ratio kept), whatever its container. The footer logo renders at
  its intended size.
- Register Visitor header: horizontal padding removed, so it aligns with
  the card.
- Create Branch "Operational Status": laid out as a normal field (label,
  then a switch plus status text on one row), aligned with its neighbour.
- Admin tables below `md`: the identifying column may wrap, the status cell
  gets `whitespace-nowrap`, and the pinned actions column gets a left
  divider and shadow. Status is never overlapped.
- Admin top bar below `md`: shows the current page's name (the active
  breadcrumb) instead of the truncated "Organization Admin". The avatar
  circle shows the user's initials, as the staff header already does.
- A repeatable visual check: `scripts/screenshot-pages.py` (from
  `assets/shoot.py`) runs in the Playwright container and captures every
  main route at 375, 768 and 1440px. It also fails when any page scrolls
  horizontally.

Out of scope: the empty Form Builder and Register Visitor step lists in
the dev tenant. Those come from an API 500: a stale `signature_pad` field
type in the data, raised with the API team separately.

## Capabilities

### New Capabilities
(none)

### Modified Capabilities
- `responsive-layout`: Adds requirements for consistent spacing between
  page sections, page headers aligned with their content, and table status
  cells never overlapped by the pinned actions column.
- `brand-identity`: Adds the requirement that the logo keeps its aspect
  ratio in any container.

## Impact

- `components/RouteTransition.tsx`, `components/BrandLogo.tsx`,
  `components/ui/responsive-table.ts` (the pinned column and wrap rules),
  `components/AdminTopBar.tsx`,
  `pages/staff-visitor-registration/Components/RegistrationWorkspaceHeader.tsx`,
  and `pages/admin-branches/admin-branch-create.tsx` (plus the branch edit
  modal, if it shares the row).
- The pages that return fragments get consistent gaps. Some pages that
  hand-added `mt-*` spacing to compensate may need that removed; this is
  checked in the screenshot pass.
- New `scripts/screenshot-pages.py`. There's no new npm dependency: it
  runs in `mcr.microsoft.com/playwright/python:v1.55.0-noble`, already
  pulled locally.

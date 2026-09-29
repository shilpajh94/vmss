## Context

See `proposal.md` - Why/Impact for the full audit findings. Three facts shape
this design:

- Every admin list page's data-fetching hook (`use-admin-branches.ts` and its
  ten siblings) independently implements "fetch everything once, filter
  client-side" — there is no shared hook for the target behavior. The one
  page that already does it right, `use-staff-audit-trail.ts` +
  `Components/Pagination.tsx`, is the reference implementation.
- `AppShell.tsx` has exactly one scroll container (`<main
  className="overflow-y-auto">`) shared by every route's content, including
  each list page's own heading/Filters/Add row.
- There is no refresh-related shared state today — each page's polling hook
  (`use-polling.ts`) and refresh button are entirely local to that page;
  `AdminTopBar.tsx` doesn't participate in refresh at all.

## Goals / Non-Goals

**Goals:**
- One shared pattern for "paginated, server-filtered list" that all eleven
  admin list pages adopt, instead of eleven bespoke reimplementations.
- One shared pattern for "heading/Filters/Add row fixed, data region
  scrolls" that any current or future list-style page can opt into, without
  changing `AppShell`'s existing behavior for non-list pages (forms,
  settings) that still rely on `<main>` itself scrolling.
- One shared refresh control, driven by whichever page is currently active,
  replacing eleven-plus hand-rolled per-page refresh buttons.
- A named spacing scale that captures the padding/gap values already in use
  today, so future pages reference tokens instead of copy-pasting pixels.

**Non-Goals:**
- No visual/branding redesign — color and type tokens (`design-theme`'s
  existing requirements) are untouched; only a spacing scale is added.
- No change to which fields are editable or validated on any create/edit
  form — this change touches list views only.
- No backend contract change beyond what the paired `VMSS_API` change
  (`add-listing-pagination-filtering`) already delivers for
  `GET /auth/permissions`. Every other endpoint this change consumes
  (`org_structure`, `visitors`, `invitations`) already accepts
  `page`/`pageSize` and typed filters today.
- No page-size *selector* in the first pass — pages ship with the API's
  default page size (20) and next/prev navigation, matching
  `staff-audit-trail`'s existing `Pagination.tsx`. Adding a page-size
  dropdown is a fast-follow, not blocking this change, since the spec's
  pagination requirements only commit to page navigation and correct
  `total`/`totalPages` display.

## Decisions

- **Shared `useServerPagedList`-style hook, adopted by each page's own
  `use-admin-*.ts` file rather than replacing those files wholesale.** Each
  page keeps its own hook (it still owns page-specific concerns: which
  fields it edits, its own create/edit/delete mutations), but its list-fetch
  concern delegates to the shared hook for page/filter state, request
  building, and reset-to-page-1-on-filter-change. Alternative considered:
  one generic `<PagedTable>` component owning fetch + render — rejected,
  because these pages differ enough in row rendering (badges, nested
  expand rows, action buttons) that forcing one render contract would fight
  the existing per-page table components more than it would save.
- **Refresh state lives in a small React context (`RefreshContext`), not a
  new global store.** Each page's data hook registers its refresh function,
  in-flight flag, and last-successful-fetch timestamp into the context on
  mount and clears its registration on unmount; `AdminTopBar` reads whatever
  is currently registered. Alternative considered: lifting every page's
  fetch into one global store keyed by route — rejected as a much bigger
  refactor than the ask requires; the navbar only needs to *trigger* and
  *observe* the active page's refresh, not own its data.
- **Sticky heading/scrollable body is a new layout component nested inside
  `AppShell`'s existing `<main>`, not a change to `<main>` itself.** The new
  component renders as a flex column filling `<main>`'s available height:
  the heading/Filters/Add row (and, when open, the filter panel) is
  `flex-none`; the data region is `flex-1 overflow-y-auto`. `<main>` keeps
  its own `overflow-y-auto` unchanged, so non-list pages (settings, forms)
  that rely on `<main>` scrolling for long content are unaffected — a list
  page using the new layout simply never grows tall enough for `<main>`
  itself to need to scroll, because its own inner region absorbs the
  overflow first.
- **The Invitations Kanban board is explicitly exempt from pagination
  controls** (see `proposal.md` - Impact). Its data-fetch is bounded (a
  generous fixed `pageSize`) but not paged, since each status column needs
  accurate full membership, not "page 1 across all statuses."
- **Spacing tokens codify today's accepted values rather than introducing
  new ones**: `p-8`/`gap-6` (page content padding / heading-to-body gap),
  `px-3.5 py-2.5` (secondary button padding), `px-[18px] py-2.5` (primary
  "Add" button padding), and `p-4` (filter panel padding) — the values the
  audit found consistently applied by copy-paste across every list page
  today — become named tokens in `theme.css`. Picking already-proven values
  avoids a visual-regression risk that inventing a new scale would carry.
- **Search-style filters (Invitations' free-text search) are debounced
  client-side before becoming a query param**, so filtering server-side
  doesn't turn every keystroke into a request.

## Risks / Trade-offs

- [Touching all eleven list pages' data hooks in one change is a wide
  blast radius] → `tasks.md` sequences Branches first (the page in the
  original bug report) to validate the shared hook and layout component,
  then rolls the same pattern to the remaining ten pages, so a problem in
  the shared pieces surfaces on page one, not page eleven.
- [The Kanban-board pagination exception could read as inconsistent to
  someone expecting "every list paginated"] → Documented with rationale in
  both `proposal.md` and the `admin-invitations` spec delta, not left
  implicit.
- [Removing each page's own refresh button changes a control users already
  rely on] → Behavior is preserved (same manual-refresh action, same
  15-second auto-refresh from `use-polling.ts`), only relocated, and gains a
  last-updated label that didn't exist before.
- [Nesting a new inner scroll region inside `AppShell`'s `<main>` risks
  interacting badly with the existing route-transition animation
  (`app-shell`'s "Route navigation is accompanied by a transition
  animation" requirement)] → `tasks.md` includes an explicit manual check
  that route transitions still play correctly for a page using the new
  sticky-heading layout before rolling it out to all eleven pages.
- [Codifying current spacing values into named tokens is a broad,
  low-risk-but-wide find/replace across every list page's markup] →
  Because the values themselves don't change (only their reference
  becomes a token instead of a literal), a visual diff before/after should
  show no pixel movement; `tasks.md` includes a visual spot-check per page.

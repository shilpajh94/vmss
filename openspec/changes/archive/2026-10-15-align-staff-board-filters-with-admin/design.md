## Context

See proposal.md for the motivation. Behavior is in
`specs/staff-dashboard/spec.md` and `specs/admin-invitations/spec.md`.

Relevant current state:

- **Shared hook.** Both pages call `useInvitationsBoard`, with
  `scope = 'mine'` for staff and `'all'` for admin. The hook already owns
  `statusFilter`/`sourceFilter` and their setters, sends `source` with the
  column query, and narrows `visibleStatuses` from `statusFilter`. So the
  staff page already has all the filter state; it just doesn't render it.
- **Admin-only clear state.** `isFiltering` and `clearFilters` are defined
  inside `admin-invitations.tsx`, not in the hook.
- **Shared filter bar.** `BoardFilterBar` already takes `extraFilters`,
  `isFiltering`, `onClearFilters`, `searchPlaceholder` and
  `trailingAction`, and always wraps.
- **Export dialog.** The staff page passes `initialStatus={''}`, while admin
  passes `statusFilter`.
- **API scoping.** The staff scope sends `relevantToMe=true`. The API ANDs
  that with `status`/`source` (`_list_filters` in VMSS_API), so a filter
  can only narrow the result.

## Goals / Non-Goals

**Goals:**
- One source of truth for the filter set and its reset, so the two boards
  can't drift.
- A staff bar that is the admin bar plus the Export button that only staff
  shows in the bar.

**Non-Goals:**
- Moving the staff Export button into the workspace header the way admin
  puts it in its title row. The bar already wraps, and the spec only
  requires that nothing clips.
- Changing what search matches. It stays visitor name or tracking ID, on
  the server; only the staff placeholder text changes.
- Persisting filters across reloads, or putting them in the URL.

## Decisions

### D1. Move `isFiltering` and `clearFilters` into `useInvitationsBoard`
The hook owns the four filter states, so it also owns "any differs from
default" and "reset all four, keep search". Both pages consume the hook's
versions, and the admin page drops its local copies.
- *Alternative:* copy the two definitions into the staff page (rejected:
  this is exactly the kind of duplication that let the bars drift apart).

### D2. Reuse `STATUS_FILTER_OPTIONS`/`SOURCE_FILTER_OPTIONS` and the same icons
The staff page passes the same `extraFilters` array shape as admin
(`CircleDotIcon` for Status, `ClipboardListIcon` for Source), built from
`filter-options.ts`. Labels, order and the Archived entry therefore always
match. A small shared helper (e.g. `boardExtraFilters(...)` next to
`filter-options.ts`) builds the array for both pages, so the icon/label
pairing also lives in one place.

### D3. Export dialog seeds from `statusFilter`
Pass `initialStatus={statusFilter}` on the staff page, as admin does. The
dialog's applied-filters summary already lists Source, because it's built
from the hook's column query.

## Risks / Trade-offs

- **The staff bar gets busier.** With a filter set and export access it
  has six controls. → `BoardFilterBar` already wraps rather than clipping
  (the 1024px Export-button fix). The spec's 1024px scenario guards this.
- **Status filter on staff.** Selecting one status hides the other
  columns, which could surprise staff used to always seeing five. → This is
  the same behavior admins already have. The column counts show zero and
  "Clear filters" is right there.

## Context

Both board pages call `useInvitationsBoard`, which already owns every filter's state and sends it to the server:

- `search`
- `purposeFilter`, with `purposeOptions`: "All purposes" plus `PURPOSE_OF_VISIT_OPTIONS` labels
- `registrationTypeFilter`
- `statusFilter`: `''` means all
- `sourceFilter`: `''` means all

Only the controls differ:

- **Staff:** `SearchActionBar` (`pages/staff-dashboard/Components/`). It has the 40px search and `DropdownFilter` selects for purpose and type, laid out `flex-col sm:flex-row sm:flex-wrap lg:flex-nowrap`.
- **Admin:** an inline pill search plus a `SlidersIcon` "Filters" button. The button toggles `isFilterPanelOpen`, which shows a `SelectField` panel for status, type and source, with a "Clear filters" link.

The admin page sits inside `PageContentLayout` under `AdminTopBar`, which already owns refresh and the user menu. The page itself only owns its "Invitations" title and the bar.

## Goals / Non-Goals

**Goals:**
- One bar component, rendered by both pages, so their look can't drift apart again.
- No change to the staff dashboard's appearance or behaviour.

**Non-Goals:**
- Changing the admin page title or `AdminTopBar`.
- The dashboard "Upcoming visitors" and "Recent check-ins" lists.
- The visitor-facing pages.
- Any change to the board hook's filtering logic or the API.

## Decisions

### 1. Promote `SearchActionBar` to a shared `BoardFilterBar` with an `extraFilters` slot

Move the component to `components/invitation-board/BoardFilterBar.tsx`, next to the board it serves, since it's no longer staff-only. It keeps its current props:

- `search` / `onSearchChange`
- `purposeFilter`, `purposeOptions`, `onPurposeFilterChange`
- `registrationTypeFilter` / `onRegistrationTypeFilterChange`

New optional props:

- `extraFilters?: Array<{ icon, value, options, onChange, ariaLabel }>`: rendered as further `DropdownFilter`s after Registration Type.
- `onClearFilters?: () => void` and `isFiltering?: boolean`: when both are set and `isFiltering` is true, a text-button "Clear filters" renders at the end of the row.

The staff page passes neither, so it renders exactly what it does now. The admin page passes Status and Source as `extraFilters`, plus the clear handler.

*Alternative considered:* hard-coding `status`/`source` props on the bar. Rejected because it leaks admin-only concepts into the staff component's API. A list of extra dropdowns is just as easy to read and stays generic.

### 2. Status and Source become `DropdownFilter`s with explicit "All" options

`DropdownFilter` is a native `<select>` with no placeholder, so each needs a real "All" option:

- Status: `{ value: '', label: 'All statuses' }` followed by the existing `STATUS_OPTIONS`.
- Source: `{ value: '', label: 'All sources' }` followed by `SOURCE_OPTIONS`.

Both keep `''` as the "no filter" value the hook already expects, so `isFiltering` and the hook stay as they are. `isFiltering` gains `purposeFilter !== 'all'`.

Icons, all already in `icons.tsx`:

| Filter | Icon |
| --- | --- |
| Status | `CircleDotIcon` |
| Source | `ClipboardListIcon` |

Purpose and Type keep the staff icons, `TagIcon` and `UsersIcon`.

### 3. Layout: one row from `xl` on the admin page

The staff bar has two dropdowns and goes to one row at `lg` (`lg:flex-nowrap`). The admin bar has four dropdowns at about 200px each. Inside the admin content area at `lg`, about 1024px minus the 280px sidebar, they can't fit beside a usable search field. So the bar's no-wrap breakpoint becomes:

- `lg:flex-nowrap` when there are no `extraFilters`: the staff page, unchanged
- `xl:flex-nowrap` otherwise

Below that the controls wrap: search on its own full-width row, dropdowns beneath. The search field keeps `sm:min-w-[240px]`.

### 4. Remove the admin toggle panel

Delete the following from `admin-invitations.tsx`:

- `isFilterPanelOpen` and its `useState` import if unused
- the pill search markup
- the `SlidersIcon`/`SearchGlyphIcon` imports, if unused
- the `SelectField` panel

The page header keeps its `<h1>Invitations</h1>` row on its own line, with the bar beneath. This matches the staff page, where the title sits above the bar.

## Risks / Trade-offs

- **Five controls make a busier bar than the staff one.** → They wrap cleanly below `xl`, and every control is the same 40px height, so the wrapped layout still reads as one group. This replaces a hidden panel, which is the inconsistency the user asked to remove.
- **Admins lose a one-click way to hide the filters.** → The filters take one row at `xl` and are small. Nothing in the specs depended on the toggle.
- **Moving `SearchActionBar` breaks any other import of it.** → It is only imported by `staff-dashboard.tsx` today. The build will catch any other import.

## Migration Plan

This is a frontend-only deploy. Rollback is reverting the commit.

## Context

See proposal.md for motivation. This is the shared design for both
`add-staff-calendar` changes (VMSS_API and VMMS_WEB).

Current state that constrains the approach:

- **Visit data.** Every visit, including walk-ins, is an `invitations` row.
  The scheduled date and time are `preferred_visit_date` (Date, required at
  creation, nullable only on legacy rows) and `preferred_visit_time`
  (nullable). Actual times are `checked_in_at` and `checked_out_at` on the
  same row. There is no recurring-invite model and no end time; there is
  only `expected_duration` (free-text label).
- **Visibility already exists, in two forms:**
  - Personal: `invitations/repository.py::relevant_to_me_clause` (clauses
    a–e, the `relevantToMe` list and `/admin/dashboard/my-*`).
  - Branch-wide: `core/tenancy.py::branch_filter` over
    `User.authorized_branch_ids("invitations:view-all")`, the default list
    and `/admin/dashboard/*`.
- **Seeded roles:**
  - host: `invitations:view` only.
  - reception, security and admin: `invitations:view-all`.
- **Web gating.** The web knows only `isAdmin` and `isReception`. It has no
  security flag and no permission list, so it cannot decide visibility
  itself.
- **Index.** `ix_invitations_branch_visit_date (branch_id,
  preferred_visit_date) WHERE deleted_at IS NULL` already exists (from
  live-dashboards-and-analytics).
- **Web stack.** The web has no date or calendar library (react 19,
  react-router 8, recharts, tailwind).

## Goals / Non-Goals

**Goals:**
- One endpoint that is the single source of truth for "which visits does
  this caller see on which day". The web never filters for visibility.
- The calendar can never show an invitation the caller could not already
  see in the invitation list or open in detail.
- Month, week and day views in the staff portal (host, reception, security)
  and the admin portal.

**Non-Goals:**
- Drag-to-reschedule or creating an invitation by clicking a slot.
  Rescheduling stays on the existing modal action.
- Recurring invitations, and exporting to iCal or Google Calendar.
- Live push updates. The page uses the existing manual and periodic refresh
  (`live-data-refresh`).
- Changing what the invitation list or dashboards return.

## Decisions

### D1. A dedicated endpoint, not a date filter on `GET /invitations`

Add `GET /invitations/calendar` rather than adding
`visitDateFrom`/`visitDateTo` to the list.

- The list is paginated (max 100), and api-conventions.md §1 requires that.
  A month grid needs every event at once, or at least exact per-day counts.
- The list item also lacks the date, host name and branch. Widening it
  would bloat every board request.
- A purpose-built response (D4) keeps the board contract untouched.

*Alternative:* list plus a date filter, with the web fetching all pages.
Rejected: 10+ sequential requests for a busy branch-month, and day totals
that are wrong until every page arrives.

*Deviation from api-conventions.md §1 (pagination):* the feed is bounded by
the 42-day range cap and a 1,000-event cap with exact `days` totals (D4),
instead of page/pageSize. It is not a human-paged list. Record this in
`docs/features/invitations.md`.

*Route order:* declare it before `GET /invitations/{invitation_id}` in
`router.py`, so `calendar` is never parsed as an id.

### D2. Scope resolved server-side with `auto`, reusing the existing predicates verbatim

`scope=auto|mine|branch` (spec "Calendar Scope Is Resolved From the
Caller's Permissions"). The service:

1. For `branch`, or for `auto` when
   `user.authorized_branch_ids("invitations:view-all")` is non-empty or
   `"all"`:
   - resolve the `BranchScope` exactly like `require_branch_scope`, with an
     optional `X-Branch-ID` passed to `authorize_branch_id`;
   - the filter is `branch_filter(Invitation.branch_id, scope)`.
2. Otherwise (`mine`, or `auto` with no view-all):
   - resolve `get_default_host_role(tenant_db)`;
   - the filter is `relevant_to_me_clause(user.id, role.id)`.

`require_branch_scope` raises inside a `Depends`. The calendar cannot gate
on it statically because `auto` and `mine` must not 403. Factor its body
into a plain helper (`resolve_branch_scope(tenant_db, user, code,
x_branch_id)` in `org_structure/deps.py`) that both the dependency and the
calendar service call. Behaviour stays identical, with one implementation.

This is why the calendar cannot disagree with the board: it composes the
same SQL predicate objects, not a re-derivation. A test asserts set
equality against `GET /invitations?relevantToMe=true` (spec "Calendar and
list never disagree for a host").

*Alternative:* the web picks the scope from `isReception`/`isAdmin`.
Rejected: security has no flag, and custom roles holding `view-all` would
be silently wrong.

### D3. Event date: scheduled date, with a check-in fallback that keeps the index

The spec defines the event date. The SQL avoids
`COALESCE(preferred_visit_date, …) BETWEEN` because that would defeat
`ix_invitations_branch_visit_date`. Instead it ORs two sargable branches:

```
(preferred_visit_date BETWEEN :from AND :to)
OR (preferred_visit_date IS NULL
    AND checked_in_at >= :from_start_utc AND checked_in_at < :to_end_utc)
```

The UTC bounds come from the **visit timezone**:
`invitations/service.py::_resolve_visit_timezone`, which uses
`Company.default_timezone`, then `Tenant.timezone`, then UTC. That is the
zone expiry and the check-in same-day gate already measure "the visit day"
in, so the calendar cannot place a visit on a different day than those do.

*Revised during apply:* the original plan moved the dashboard's
tenant-only `_resolve_tenant_timezone` to `core/`. That would have ignored
the company timezone admins actually edit. The dashboard is left
untouched.

The fallback branch's event date is computed in SQL as
`timezone(:tz, checked_in_at)::date`, so the `GROUP BY` day totals and the
event rows agree. It affects a handful of legacy rows at most.

Week and day views place events by scheduled `time`. Events with a null
time go in an "Any time" row. Actual check-in and check-out times are shown
on the event, not used for placement. That keeps an event in the same slot
across views and after the visit happens.

### D4. Response shape: exact day totals plus a capped event list

```
CalendarFeedOut {
  scope: "mine" | "branch"
  timezone, from, to, generatedAt
  days: [{ date, total }]            // every date in range, GROUP BY in SQL
  events: [CalendarEventOut]         // ≤ 1000, ordered date, time NULLS LAST, name
  truncated: bool
}
```

The repository runs two statements against the same filter list:

- a `GROUP BY event_date` count;
- an event select `LIMIT 1001`. Fetching 1,001 rows detects truncation
  without a third `COUNT`.

Python fills zero days. For host and branch display names, the event
select uses `outerjoin(User, User.id == Invitation.host_id)`, `Branch` and
`Building`, and a `VisitorCategory` join. `visitorCount` comes from a
correlated `count()` subquery on `invitation_visitors` (+1 for the primary
contact). Everything is in one statement, with no per-row loading
(query-performance.md §2). Selecting columns, not ORM entities, avoids
`MissingGreenlet` risk on relationships.

The cap of 1,000 is about 33 events a day across a 30-day month. Above
that, a month cell shows "+N more" from `days` anyway, and the web asks for
a narrower range (week or day) to list them.

### D5. Default status set excludes `denied` only

`archived` (the lifecycle sweep's missed or expired visit) stays visible by
default, because a missed visit is useful history on a calendar. `denied`
never happened and would clutter the grid. The web exposes a status filter
to add it back.

### D6. Web: hand-built views on native `Intl`/`Date`, no calendar library

Build `MonthGrid`, `WeekView` and `DayAgenda` components on the existing
tailwind theme, using `Intl.DateTimeFormat` for labels.

- Events have no reliable end time, so a full time-grid engine
  (FullCalendar, react-big-calendar) would spend most of its weight on
  overlap layout we cannot feed.
- Week and day views are hour-bucketed lists (an "Any time" row plus hour
  rows), not absolutely positioned blocks. That sidesteps overlap layout
  entirely.

Date arithmetic needs only "start of week", "add days" and "month grid
start". These are local-date-only operations on `YYYY-MM-DD` strings, in a
small pure `calendar-dates.ts` util that never touches the browser timezone.
VMMS_WEB has no unit-test runner, so these are covered by the e2e month,
week and day navigation tests rather than by adding one.

- The week starts on Monday.
- "Today" is the server's tenant-local date. The web derives it from the
  response's `timezone`, never from the browser's zone, matching the
  dashboards' `today` handling.

*Alternative:* `@fullcalendar/react` (MIT core). Rejected for bundle size
(~100 KB gz), a second styling system to theme against design-theme, and
little value without end times.

### D7. Web routes and navigation

- `/staff/calendar` (inside `StaffLayout`, so it serves host, security and
  reception) and `/admin/calendar` (inside `AdminLayout`). Both are thin
  wrappers around one `CalendarPage` component.
- A "Calendar" nav item goes in `DashboardSidebar`, `ReceptionSidebar` and
  `AdminSidebar` (after Dashboard and Invitations respectively), with
  `resolve*ActiveItem` prefix entries.
- The branch selector shows only when the response `scope` is `branch` and
  the user has more than one authorized branch. It sends `X-Branch-ID`.
  "All branches" omits the header.
- A "Mine / Branch" toggle is not exposed. The user chose role-default
  scoping. The API supports `scope=mine` for a later toggle at no cost.
- Clicking an event navigates to the existing board deep link
  (`buildInvitationPath` →
  `/staff/invitations?invitationId=` or `/admin/invitations?invitationId=`),
  which opens `VisitorInfoModal` with all its actions. This reuses one
  detail surface instead of duplicating the modal's action wiring.
- Detail visibility (`GET /invitations/{id}`) already admits branch-wide
  viewers and participants, so every event the calendar shows can be
  opened.

### D8. Visual encoding

Each event chip shows time, primary contact name (+N co-visitors), and a
status colour token:

| Status | Shown as |
|---|---|
| submitted | Pending |
| approved | Expected |
| checked_in | Inside |
| checked_out | Visited |
| archived | Missed |
| denied | Denied, only when filtered in |

- The visitor-category badge colour is a left border.
- Host name and branch show on hover or focus and in the day view, and only
  when `scope` is `branch` (for `mine`, the host is usually the viewer).
- Colours come from design-theme tokens, with light and dark parity.

## Risks / Trade-offs

- **Branch-scope helper refactor.** A refactor of `require_branch_scope`
  could change list behaviour. → Pure extraction, with the existing list
  scope tests run unchanged plus a direct helper test.
- **`auto` surprises a reception user** who expects their personal
  worklist. → It matches the user's chosen rule (branch-wide for
  view-all). The response `scope` is shown in the page subtitle ("All
  visits at Branch A" vs "Your visits").
- **Cap truncation on huge branches.** → Exact `days` totals and a
  "Showing first 1,000 — switch to week view" banner. Logged at INFO with
  the tenant, range and count, to see whether the cap is ever hit in
  practice.
- **Legacy rows without a visit date** cost an OR branch. → Both arms are
  index-friendly. If needed, `ix_invitations_branch_checked_in_at` covers
  the second.
- **Reschedule race.** A visit rescheduled between fetch and click opens on
  its new date in the modal. → Acceptable. The page refetches on the
  modal's close.

## Migration Plan

- API: additive route, no migration, no new setting. Deploy the API first.
  The web change is inert until its routes ship.
- Rollback: revert the web nav items and routes. The API route is unused
  but harmless and can stay.

## Open Questions

- Should the week start come from a tenant setting (Sunday-start locales)?
  Monday is hard-coded for now. Adding a setting later is additive and does
  not change these specs' scoping rules.

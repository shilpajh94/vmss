## Why

Staff have no way to see visits laid out over time. Today a host,
receptionist or security officer can only scroll the invitation board, which
is sorted by status change, not by visit date. "Who is coming on Thursday?"
or "how busy is next week at this branch?" cannot be answered without
paging through the list.

The invitation list cannot back a calendar as it stands:

- It has no visit-date range filter. The only date filter is on the export
  endpoint, and it filters status timestamps, not the visit date.
- Its list item does not return `preferredVisitDate`, `preferredVisitTime`,
  the host's name or the branch.
- It is paginated 100 rows at a time, so the web would have to fetch every
  page of a month to fill one grid.

A calendar must also be correct per role. A host must never see another
host's visitors. Reception and security must see their whole branch, and
nothing outside the branches they are authorized for.

This change has a companion change of the same name in VMMS_WEB. That change
holds the web specs and tasks. This one holds the API contract and the
shared design.

## What Changes

- **New calendar endpoint.** `GET /api/v1/invitations/calendar?from=&to=&scope=&status=`
  returns every invitation and walk-in whose visit falls between two local
  dates (inclusive). The range is at most 42 days, which is one six-week
  month grid.
- **Scope is decided by the server, not the client.**
  - `scope=mine` is the caller's `relevantToMe` set (host, delegate,
    approver), the same predicate as `GET /invitations?relevantToMe=true`.
  - `scope=branch` is every invitation at the caller's authorized branches.
    It requires `invitations:view-all`. `X-Branch-ID` narrows it to one
    branch, the same way it narrows the invitation list.
  - `scope=auto` (the default) resolves to `branch` when the caller holds
    `invitations:view-all` at any branch, and to `mine` otherwise.
  - The response says which scope was applied.
  - With the seeded roles, this means a host sees `mine`, while reception,
    security and admin see `branch`.
- **Event date rule.** An event falls on its `preferred_visit_date`. For a
  legacy row with no visit date, it falls on the visit-timezone date of its
  check-in. Times are the scheduled `preferred_visit_time`. Actual check-in
  and check-out times are returned alongside.
- **Correct day totals even when truncated.** The response carries a
  per-day count computed in the database. The event list is capped at 1,000
  rows and is flagged `truncated` when it hits the cap. Day totals in a
  month view therefore never undercount.
- **Status filter.** By default every status except `denied` is returned:
  `submitted`, `approved`, `checked_in`, `checked_out`, and `archived`
  (missed or expired). A repeatable `status` parameter overrides the
  default.
- **Minimal data per event.** Each event carries the tracking id, primary
  contact name, visitor count, status, scheduled date and time, expected
  duration, actual check-in and check-out times, host id and name, branch,
  building, purpose, visitor category and badge colour, and source. It does
  not carry phone numbers, email addresses, ID-proof data or photos.

## Capabilities

### New Capabilities
- `invitation-calendar`: the date-ranged, role-scoped calendar feed of
  invitations and walk-ins for staff.

### Modified Capabilities
<!-- None. The invitation list and dashboard contracts are unchanged; the calendar reuses their visibility predicates without altering them. -->

## Impact

- **API (additive, `v1`):** one new route, `GET /invitations/calendar`, with
  new `CalendarQuery` / `CalendarFeedOut` / `CalendarEventOut` schemas in
  `invitations/schemas.py`.
- **Code:**
  - `invitations/router.py`, `service.py` and `repository.py`.
  - Reuses `relevant_to_me_clause`, `branch_filter`,
    `User.authorized_branch_ids`, `get_default_host_role` and the dashboard's
    tenant-timezone resolution.
- **Database:** no migration. The existing partial index
  `ix_invitations_branch_visit_date (branch_id, preferred_visit_date)`
  covers the range scan.
- **Docs:** `docs/features/invitations.md` gains a Calendar section.
- **Web:** VMMS_WEB `add-staff-calendar` consumes the endpoint. Deploy this
  API change first.

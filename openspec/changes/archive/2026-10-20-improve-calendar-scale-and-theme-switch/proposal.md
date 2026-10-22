## Why

Busy branches have 100+ visits on a single day (the QA tenant already has
181 on one Monday). The calendar feed returns every visit in the range in
one response, capped at 1,000. That causes two problems:

- **The week view can't hold a busy day.** It renders every visit at once,
  so the page grows into an endless scroll.
- **Visits get dropped.** A week with more than 1,000 visits silently loses
  the rest. The page only shows a "not every visit is listed" banner.

The staff portal is moving to day columns that show the first 10 visits
and load more as the user scrolls. The API needs to serve visits a page at
a time per day. Every day must stay reachable, and the per-day totals must
stay exact.

This change has a companion change of the same name in VMMS_WEB, which
holds the web specs and tasks and the shared design. This one holds the
API contract.

## What Changes

- **`perDayLimit` on the calendar feed.** `GET /invitations/calendar` gains
  an optional `perDayLimit` (1–100):
  - When it is set, `events` holds at most that many visits per day: the
    first ones in the standard order (time, any-time last, then name).
  - `days[].total` stays exact.
  - Without it, the response is unchanged, so existing clients are
    unaffected.
  - The web asks for 3 per day in Month view (that's all a cell shows) and
    10 per day in Week view. A 42-day month then returns at most 126
    visits instead of up to 1,000.
- **A paged day endpoint.** `GET /invitations/calendar/day?date=&page=&pageSize=`
  returns one day's visits through the standard pagination envelope
  (`pageSize` defaults to 20, max 100):
  - It applies the same scope, `X-Branch-ID`, status filter, event-date
    rule, ordering and display-only fields as the feed.
  - Page 1 with `pageSize=10` is exactly the first 10 the feed returns for
    that day, so the web can append page 2, 3… without gaps or overlaps.
- **Stable order.** Both endpoints break ties on the invitation id after
  date, time and name, so offset paging never repeats or skips a visit.

Both are additive `v1` changes, so there is no breaking change.

## Capabilities

### New Capabilities
<!-- None -->

### Modified Capabilities
- `invitation-calendar`: adds the `perDayLimit` feed option and the paged
  per-day endpoint. The tie-break on id is added to the ordering rule in
  "Day Totals Are Exact and the Event List Is Bounded".

## Impact

- **Code:**
  - `invitations/schemas.py`: `perDayLimit`, and `CalendarDayPageQuery`
    reusing `CalendarEventOut`.
  - `invitations/repository.py`: a windowed per-day query
    (`row_number() OVER (PARTITION BY event_date …)`) and a single-day
    offset query.
  - `invitations/service.py` and `invitations/router.py`: the new route,
    registered before `/{invitation_id}`.
- **Database:** no migration. The single-day query hits
  `ix_invitations_branch_visit_date` with an equality on the date.
- **Docs:** `docs/features/invitations.md` Calendar section.
- **Web:** VMMS_WEB `improve-calendar-scale-and-theme-switch` uses both.
  Deploy this API change first.

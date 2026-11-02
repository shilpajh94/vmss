## Why

The admin, reception and staff dashboards show numbers that look wrong to
the people using them. A tile says one thing, and the list it opens shows
something else. Some figures disagree with each other on the same page.

What was found:

1. **Pending Approval counts requests whose visit is already over.**
   Requests stay `submitted` forever once their visit window passes,
   because nothing closes them. Locally, 174 of 192 pending requests were
   already expired. "Oldest waiting" is measured from those dead
   requests, so it reads in days.
2. **"N checked in so far" can be bigger than "Expected Today".** The
   detail counts every check-in made today, including visitors scheduled
   for other days. The tile it sits under counts only today's scheduled
   visits.
3. **No list can show what a tile counts.** `GET /invitations` filters by
   status only. "Expected Today" (dated today), "Upcoming" (not expired,
   never admitted), the status chart (dated within the range), and a
   dashboard's selected branch can't be expressed as list filters. So
   every link lands on a broader list than the number it came from.
4. **The dashboard uses a different timezone from the rest of the
   system.** Invitations date a visit and set its expiry in the visit
   timezone: the company's default timezone (the one admins edit in org
   setup), else the tenant's. The dashboard uses only the tenant's
   provisioning timezone. For a company on `Asia/Kolkata` under a `UTC`
   tenant, this has two effects:
   - From midnight to 05:30, "today" on the dashboard is yesterday.
   - The arrivals-by-hour chart is shifted by 5½ hours.
5. **Two different date rules.** "Expected Today", the traffic trend and
   the top-label charts date a visit by its scheduled visit date only. The
   status breakdown falls back to the creation date when there is none. A
   visit with no date can then count on one and not the other.

## What Changes

- **New overview fields** (additive; the old fields stay, deprecated, the
  same way `visitsTodayCount` was handled):
  - `scheduledTodayCheckedInCount`: today's scheduled visits that have
    been checked in at least once. It replaces `checkedInTodayCount` as
    the "checked in so far" detail. `checkedInTodayCount` itself is
    unchanged and still matches the hourly arrivals chart.
  - `openPendingApprovalCount` and `oldestOpenPendingSubmittedAt`: pending
    requests whose visit window hasn't closed yet (`expiresAt` in the
    future). `pendingApprovalCount` and `oldestPendingSubmittedAt` are
    deprecated.
  - On `my-overview`: `openAwaitingApproval`, the same rule over the
    caller's own visits. `awaitingApproval` is deprecated.
- **The dashboard uses the visit timezone** (company default, else
  tenant, else UTC) for "today", every date range, the hourly chart and
  the `timezone` it reports. This is the same resolution invitations
  already use, shared rather than copied.
- **One "visit day" for every dashboard figure.** A visit is dated by its
  scheduled visit date, or by its tenant-local creation date when it has
  none. This applies to Expected Today / Visits Today, the trend, the top
  labels and the status breakdown. Local data has no undated invitations,
  so today's numbers don't move. The rule only removes the edge case.
- **New list filters on `GET /invitations`** (and `GET /invitations/export`,
  which shares the same filter set). All are optional and additive:
  - `visitDateFrom` / `visitDateTo`: the same visit-day rule as above;
  - `upcoming=true`: exactly the dashboard's "upcoming" filter;
  - `excludeExpired=true`: only invitations whose `expiresAt` is in the
    future;
  - `branchId`: narrows to one branch. In the branch-scoped mode the
    caller must be authorized there (403 otherwise). In `relevantToMe`
    mode it only narrows the caller's own set and never widens it.
- Each dashboard count and its list filter are built from one shared
  definition in code, so the two can't drift apart again.
- No data is changed. No sweep or migration is involved.

## Capabilities

### New Capabilities

_None._

### Modified Capabilities

- `dashboard`: "Dashboard Overview Summary" and "Personal Dashboard
  Overview…" gain the new fields and the visit-day rule. "Branch-Wide
  Dashboard Analytics" defines the visit timezone and the visit day used
  by every dashboard figure.
- `invitations`: adds the drill-down list filters.

## Impact

- Code: `dashboard/repository.py`, `dashboard/service.py`,
  `dashboard/schemas.py`, `invitations/repository.py` (`_list_filters`),
  `invitations/router.py` (list and export params), and
  `invitations/service.py` (passes the tenant timezone into the list).
- API: additive only. No `v2` is needed. The deprecated fields stay until
  their removal date in `docs/features/dashboard.md`.
- Docs: `docs/features/dashboard.md` and `docs/features/invitations.md`.
- Web: the VMMS_WEB change of the same name (`fix-dashboard-count-accuracy`)
  switches the tiles, cards and charts to the new fields and filters. Ship
  the API first. Until the web change ships, nothing visible changes.

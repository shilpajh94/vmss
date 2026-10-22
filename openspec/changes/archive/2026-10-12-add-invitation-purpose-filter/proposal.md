## Why

The web Visits board (staff dashboard and admin Invitations board) is moving
from "fetch 100 rows, then filter in the browser" to per-status columns that
lazy-load 20 rows at a time from `GET /invitations`. This is the paired web
change `board-sticky-headers-lazy-load` in `VMMS_WEB`.

Once the board fetches pages, every filter has to run on the server. Filtering
in the browser would only filter the pages already loaded, and the column
counts (`pagination.total`) would ignore the filter. `status`, `search`, and
`registrationType` already exist on `GET /invitations`. The board's "All
purposes" dropdown has no server-side equivalent.

## What Changes

- `GET /invitations` gains an optional `purposeOfVisit` query parameter
  (max 255 characters). When present, it narrows results to invitations whose
  `purpose_of_visit` equals the given value exactly. It combines with the
  existing `status`, `registrationType`, `source`, `search`, and
  `relevantToMe` filters using `AND`, and applies no filter when omitted.
  `pagination.total` reflects the filtered count.
- This is additive: no existing parameter or response field changes, so it is
  not breaking (`api-conventions.md` §2).

## Capabilities

### New Capabilities

(none)

### Modified Capabilities

- `invitations`: `GET /invitations` accepts a `purposeOfVisit` filter. This is
  added as its own requirement, not as an edit to "Employee Lists Invitations
  at Their Authorized Branches". Several unarchived changes already carry
  deltas against `invitations`, and the earlier `search` filter
  (`add-listing-pagination-filtering`) used the same `ADDED`-requirement
  pattern for the same reason.

## Impact

- **Code:** `src/vmss_api/invitations/router.py` (`list_invitations`: new
  `Query(alias="purposeOfVisit", max_length=255)` param),
  `service.py` (`list_invitations_page` passes it through), and
  `repository.py` (`InvitationRepository.list_page`: one more equality filter).
  The response schema does not change.
- **Tests:** `src/vmss_api/invitations/tests.py`, plus the direct
  `list_page`/`list_invitations_page` call sites in that file that pass every
  keyword explicitly (around lines 4498 and 4539).
- **Docs:** `docs/features/invitations.md` list-endpoint parameter table.
- **Performance:** no new index. The filter always combines with the
  branch-scope or `relevantToMe` predicate and usually with `status`, so the
  existing plan narrows rows first. Revisit only if `EXPLAIN` on a large tenant
  shows a sequential scan driven by this predicate.
- **Clients:** the web board sends this param. Older clients that don't send it
  are unaffected.

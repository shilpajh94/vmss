## Why

The staff/desk-facing check-in endpoint (`PATCH /api/v2/invitations/{trackingId}/check-in` —
spec.md "Staff Check-In Has One Canonical Endpoint") only admits an invitation whose
`status` is `approved`. Once a visitor checks out (`status` becomes `checked_out`, via
either the staff-authenticated `PATCH /invitations/{id}/check-out` route or a QR
check-out scan), that same visitor can never be checked back in through this endpoint —
every retry is rejected with `409 Invitation is not approved`. In practice this means a
visitor who steps out and comes back (lunch, a second delivery drop-off, moving between
buildings on a multi-building site) is permanently locked out for the rest of that
invitation's validity window.

The QR check-in/check-out pair already solves exactly this problem for its own path —
`checkInStatus` cycles `unused`/`checked_out` → `checked_in` → `checked_out` indefinitely,
with no terminal state (spec.md "QR Check-In Endpoint Transitions an Eligible Visitor to
Checked-In"). The tracking-ID canonical endpoint needs the same re-entry behavior so a
kiosk, staff desk, or visitor device using tracking-ID check-in isn't stricter than the
QR path for the identical real-world scenario.

## What Changes

- `PATCH /api/v2/invitations/{trackingId}/check-in` admits an invitation whose
  `checkInStatus` is `unused` **or** `checked_out` (previously: only reachable once, from
  `status == approved`), mirroring the QR endpoint's cycling rule. `status` must still
  reflect that the invitation was actually approved at some point (i.e. currently
  `approved`, `checked_in`, or `checked_out` — not `submitted`, `denied`, or expired-out),
  and the watchlist-flagged and expiry gates are unchanged.
- **Amended during implementation, at Reception's explicit request**: calling
  a check-in endpoint while already `checked_in` (`checkInStatus == checked_in`)
  is a `200` idempotent no-op (unchanged data, no re-stamped `checkedInAt`, no
  duplicate host notification or audit entry) rather than the `409` originally
  planned above — both endpoints are still entry-only (a checked-in visitor
  still exits via the check-out routes; a repeat check-in call never toggles
  to checked-out), but a redundant/duplicate check-in call is no longer an
  error on either endpoint. Because both check-in endpoints share the one
  `check_in_status` column, this idempotency holds *across* endpoints too —
  checking in via tracking-ID then "checking in" again via QR (or vice versa)
  is recognized as the same already-checked-in visitor and returns 200, not
  409/500 or a second write.
- The staff-authenticated `PATCH /invitations/{id}/check-out` route and the QR
  check-out route are unchanged — either can close out a re-opened check-in the same
  way they close out the first one.
- No change to the one-canonical-endpoint rule itself, to the badge/notification
  behavior, or to any response shape — only the eligibility gate the repository's
  atomic `UPDATE` checks.

## Capabilities

### Modified Capabilities
- `invitations`: the tracking-ID check-in requirement ("Staff Check-In Has One Canonical
  Endpoint") gains a re-entry rule so `checked_out` is no longer a terminal state for
  this endpoint, matching the QR check-in/check-out cycling rule already in force for
  "QR Check-In Endpoint Transitions an Eligible Visitor to Checked-In".

## Impact

- `src/vmss_api/invitations/repository.py::check_in_if_eligible` — widen the atomic
  `WHERE` clause from `status == "approved"` to admit `checkInStatus in (unused,
  checked_out)` (plus the existing watchlist-flagged guard), and set `check_in_status`
  alongside `status` on the transition, the same way `check_in_by_qr_if_eligible`
  already does.
- `src/vmss_api/invitations/service.py::_perform_check_in` — relax the pre-check from
  `invitation.status != "approved"` to the broader eligibility check described above, so
  the 409 reason string stays accurate for each rejection case.
- No model/migration change: `check_in_status` already exists on `Invitation`
  (`add-qr-checkin-security`) and is simply read/written by one more code path.
- No API contract change (same route, same request/response shape) — existing callers
  of the tracking-ID check-in endpoint are unaffected except that a previously-rejected
  retry after checkout now succeeds.

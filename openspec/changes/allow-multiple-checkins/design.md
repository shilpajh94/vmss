## Context

`Invitation` carries two parallel lifecycle columns (`invitations/models.py`):
`status` (overloaded — also carries `submitted`/`approved`/`denied` from the
approval workflow) and `check_in_status` (`unused` → `checked_in` →
`checked_out`, added by `add-qr-checkin-security` specifically so the QR
check-in/check-out pair could cycle without touching `status`'s existing
semantics for other readers, e.g. the emergency "who's inside" report).

Today the two columns are kept in lockstep by different code for different
paths:
- QR path (`check_in_by_qr_if_eligible` / `check_out_by_qr_if_eligible` in
  `invitations/repository.py`) gates on `check_in_status` and writes both
  columns together — this is the path that already cycles indefinitely.
- Tracking-ID/staff path (`check_in_if_eligible` / `check_out_if_checked_in`)
  gates and writes `status` only, and never reads or writes
  `check_in_status` at all. This is why `checked_out` is effectively
  terminal for this path: once `status` leaves `approved`, the WHERE clause
  in `check_in_if_eligible` can never match again.

See proposal.md - Why for the user-facing symptom this causes.

## Goals / Non-Goals

**Goals:**
- Let the tracking-ID/staff check-in path cycle the same way the QR path
  already does, reusing `check_in_status` as the re-entry gate instead of
  introducing a third lifecycle representation.
- Keep `status` a meaningful single source of truth for "is this invitation
  currently checked in" (readers like the emergency report key off `status
  == checked_in`, not `check_in_status`), so both columns stay written
  together on every transition, on every path.

**Non-Goals:**
- Collapsing `status` and `check_in_status` into one column. `status` still
  needs its `submitted`/`approved`/`denied` values for the approval
  workflow; that merge is out of scope here and not needed to fix this bug.
- Changing check-out behavior, badge issuance, notification behavior, or the
  QR endpoints — all unchanged.
- Adding a check-in *history* (a log of every check-in/check-out timestamp
  pair). `checked_in_at`/`checked_out_at` continue to hold only the most
  recent cycle's timestamps, same as the QR path already does today; a full
  audit trail of each cycle already exists separately via `AuditLog`
  (`security-architecture.md` §5) and is out of scope for this change.

## Decisions

**Gate `check_in_if_eligible` on `check_in_status`, not `status`.**
Change the atomic `UPDATE ... WHERE` in
`invitations/repository.py::check_in_if_eligible` from
`Invitation.status == "approved"` to
`Invitation.check_in_status.in_(("unused", "checked_out"))` AND
`Invitation.status.in_(("approved", "checked_in", "checked_out"))` (the
second clause preserves "must have been approved at some point" — a
`submitted` or `denied` invitation still can't check in) AND
`Invitation.watchlist_flagged.is_(False)` (unchanged). On success, the
`VALUES` clause sets both `status="checked_in"` and
`check_in_status="checked_in"`, matching what `check_in_by_qr_if_eligible`
already does. This is a direct port of the QR path's already-proven pattern
rather than a new design — same rationale, same shape, one gate reused by
both entry points.
_Alternative considered_: gate on `status` alone by removing `status`'s
transition-to-`checked_out`-is-terminal behavior (e.g. allow `status ==
"checked_out"` to also re-enter). Rejected: `check_in_status` already exists
for exactly this purpose and is proven by the QR path; duplicating the same
cycling logic against `status` would mean two independent representations
of "is this visitor currently inside" that could drift out of sync with
each other over multiple cycles.

**`check_out_if_checked_in` also writes `check_in_status`.**
The staff-authenticated check-out path
(`invitations/repository.py::check_out_if_checked_in`) currently only reads
and writes `status`. It must additionally set
`check_in_status="checked_out"` in the same `UPDATE`, otherwise a visitor
checked in via the tracking-ID path and checked out via the staff-authenticated
path would leave `check_in_status` stuck at `checked_in` forever (it was
never advanced past its default on the way in, either — this fix also
requires `check_in_if_eligible` to set `check_in_status="checked_in"` on
entry, per the decision above), permanently blocking the very re-entry this
change exists to enable. The gate itself (`status == "checked_in"`) is
unchanged.

**Service-layer pre-check in `_perform_check_in` mirrors the new gate — amended
to an idempotent no-op, not a 409, for the already-checked-in case.**
`invitations/service.py::_perform_check_in`'s pre-check (originally
`if invitation.status != "approved": raise 409 "Invitation is not
approved"`) becomes:
1. `if invitation.check_in_status == "checked_in": return invitation,
   changed=False` — **amended during implementation, at Reception's
   explicit request**: a repeat check-in call while already `checked_in` is
   a `200` idempotent no-op (unchanged data), not the `409 "Invitation is
   already checked in; use check-out instead"` originally planned. Checked
   *before* the watchlist gate below, deliberately — a flag added after a
   visitor already entered must not turn their harmless repeat call into an
   error. `check_in_by_qr_token` gets the identical amendment for the same
   reason, so both endpoints treat "already checked in" the same way,
   including across each other (§ below).
2. `if invitation.watchlist_flagged: raise 409 "...watchlist..."` (unchanged
   — still blocks a genuine new entry attempt).
3. `if invitation.status not in ("approved", "checked_in", "checked_out"):
   raise 409 "Invitation is not approved"` (never-approved gate, existing
   message preserved for this case since it's still the accurate reason).

This is a pre-check only — the repository's atomic `UPDATE` (above) is still
the actual race-safe gate for an actual transition, same division of
responsibility `_perform_check_in`'s existing docstring already describes.
The idempotent-no-op branch performs no repository call at all, so there is
no race to guard there: two concurrent calls that both observe
`check_in_status == "checked_in"` both just return the same unchanged row.

**Router-level: skip the audit-log write on the idempotent-no-op path.**
Both `_perform_check_in` and `check_in_by_qr_token` now return an extra
`changed: bool` alongside the invitation (and, for the QR path, the
message) — `False` for the no-op branch above. `invitations/router.py`'s two
check-in routes only enqueue their `record_audit_log` background task when
`changed` is `True`, so a redundant/duplicate check-in call (including the
cross-endpoint case) does not write a misleading "checked in" audit entry
for an invitation that was, in fact, already checked in.

## Risks / Trade-offs

- [Two columns updated together on two paths (tracking-ID and QR) plus one
  path from check-out] → each transition writes both `status` and
  `check_in_status` in the same atomic `UPDATE` statement (never two
  separate statements), so there is no window where they can disagree
  within one request. This is the same guarantee the QR path already
  relies on.
- [Existing rows checked out before this change ships have `check_in_status
  == "checked_out"` already, since the QR path has been writing it all
  along for QR-driven checkouts — but any invitation whose *only* check-out
  ever happened via the staff-authenticated `check_out_if_checked_in` path
  before this change never had `check_in_status` advanced past its default
  (`"unused"`) on check-in in the first place] → harmless: `"unused"` is
  itself one of the two admitted values in the widened gate, so a
  pre-existing row in that state is still correctly re-enterable, not
  incorrectly blocked or incorrectly already-eligible-forever.
- [Broader `status` gate now admits `checked_in` as a starting value for the
  eligibility pre-check, not just `approved`] → not a new entry path: an
  invitation whose `status` is `checked_in` is always short-circuited first
  by the `check_in_status == "checked_in"` idempotent-no-op branch, so this
  clause is never actually reached in that state. It exists purely to keep
  the "was this ever approved" condition true across the whole `approved` →
  `checked_in` → `checked_out` → `checked_in` cycle.
- [Idempotent no-op means a genuinely malicious/erroneous duplicate call is
  indistinguishable from a legitimate retry] → accepted: the only
  information lost is a 409 that would have told a caller "you already did
  this," which the caller can equally infer from the 200 response's
  unchanged `checkedInAt`/`status` if it cares to check. No security
  boundary depends on this being an error — check-in is a public,
  unauthenticated action gated only by possessing a valid tracking ID or QR
  token, same as before.

## Migration Plan

No schema migration: `check_in_status` already exists on `Invitation`
(`add-qr-checkin-security`) with default `"unused"`. This is a pure
application-logic change — deploy the updated `repository.py`/`service.py`
together (both must ship in the same release; shipping the repository
change without the service-layer pre-check would produce a 409 with a
misleading pre-check reason before ever reaching the corrected `UPDATE`).
No feature flag: the corrected behavior is strictly less restrictive than
today's and matches an already-shipped, already-tested code path (QR
check-in), so no rollout gating is needed. Rollback is a plain revert if
needed.

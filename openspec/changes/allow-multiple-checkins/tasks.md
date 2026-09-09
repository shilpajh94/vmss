## 1. Repository layer

- [x] 1.1 In `invitations/repository.py::check_in_if_eligible`, widen the
      atomic `UPDATE ... WHERE` clause to
      `Invitation.check_in_status.in_(("unused", "checked_out"))` AND
      `Invitation.status.in_(("approved", "checked_in", "checked_out"))` AND
      `Invitation.watchlist_flagged.is_(False)`, and add
      `check_in_status="checked_in"` to the `VALUES` clause alongside the
      existing `status`/`checked_in_at`/`checked_in_by_user_id` columns.
- [x] 1.2 In `invitations/repository.py::check_out_if_checked_in`, add
      `check_in_status="checked_out"` to the `VALUES` clause alongside the
      existing `status`/`checked_out_at`/`checked_out_by_user_id` columns.
      Gate (`Invitation.status == "checked_in"`) unchanged.
- [x] 1.3 Update both methods' docstrings to describe the cycling behavior,
      matching the style of `check_in_by_qr_if_eligible`'s existing
      docstring (design.md - Decisions).

## 2. Service layer

- [x] 2.1 In `invitations/service.py::_perform_check_in`, replace the single
      `if invitation.status != "approved"` pre-check with ordered checks —
      **amended during implementation, at Reception's explicit request**:
      (a) `check_in_status == "checked_in"` → return the invitation
      unchanged as a `200` idempotent no-op (not the originally-planned 409),
      checked before the watchlist gate; (b) `watchlist_flagged` → 409
      (unchanged); (c) `status not in ("approved", "checked_in",
      "checked_out")` → 409 "Invitation is not approved". Applied the
      identical amendment to `check_in_by_qr_token`'s equivalent check so
      both endpoints — and the cross-endpoint case — treat "already checked
      in" as success, not an error. See design.md's amended "Service-layer
      pre-check" decision.
- [x] 2.2 Confirm `check_in_invitation_by_tracking_id` and any other caller
      of `_perform_check_in` need no changes beyond this (they only pass
      through to it) — both now also propagate a `changed: bool` so
      `invitations/router.py` can skip the audit-log write on the
      idempotent-no-op path (design.md's "Router-level" decision).

## 3. Tests (`invitations/tests.py`)

- [x] 3.1 Add a test: check in an `approved` invitation, check it out via
      the staff-authenticated check-out endpoint, then check in again via
      `PATCH /api/v2/invitations/{trackingId}/check-in` — assert 200 and
      that `checkInStatus`/`status` both read `checked_in` with a refreshed
      `checkedInAt`. (`test_public_check_in_re_entry_after_staff_checkout_succeeds`)
- [x] 3.2 Add a test: repeat the check-in → check-out → check-in cycle a
      third time (two full round trips) — assert every cycle succeeds.
      (`test_public_check_in_two_full_round_trips_succeed`)
- [x] 3.3 Add a test: calling `PATCH /api/v2/invitations/{trackingId}/check-in`
      while `checkInStatus` is already `checked_in` returns **200 as an
      idempotent no-op** (amended during implementation — see proposal.md)
      and leaves `checkedInAt` unchanged (regression guard for the
      entry-only + idempotent rule).
      (`test_public_check_in_while_already_checked_in_is_idempotent_success`,
      plus `test_qr_check_in_while_already_checked_in_is_idempotent_success`
      for the QR endpoint's identical amendment)
- [x] 3.4 Add a test: an invitation with `status == "submitted"` (never
      approved) is still rejected with 409 by the tracking-ID check-in
      endpoint — regression guard that the "must have been approved" gate
      still holds. Already covered by the pre-existing
      `test_public_check_in_non_approved_rejected`; re-verified green
      against the new gate, no change needed.
- [x] 3.5 Add a test: a watchlist-flagged invitation that was previously
      checked in and checked out is still rejected with 409 when re-entry
      is attempted — regression guard for the existing watchlist gate
      surviving the widened eligibility check.
      (`test_public_check_in_watchlist_flagged_still_blocked_after_checkout`)
- [x] 3.6 Confirm/adjust any existing test that asserted a post-checkout
      check-in attempt fails with 409 "Invitation is not approved" — that
      assertion is now incorrect and must be replaced with the new
      succeeds-on-re-entry expectation (see 3.1). No existing test made this
      assertion for the tracking-ID path (only the QR path had cycling
      coverage before this change) — confirmed via grep, nothing to adjust.
- [x] 3.7 (Added beyond the original scope, found via live reproduction
      against the dev server, not just test review): the actual root-cause
      bug this change closes was a **cross-path** gap, not just "checkout is
      terminal on one endpoint" — because the tracking-ID path never wrote
      `check_in_status`, a visitor checked in via tracking-ID could be
      checked in *again* via the QR endpoint (and vice versa) with no
      check-out in between, since each endpoint's gate read a different
      column. Added `test_check_in_via_tracking_id_then_qr_is_idempotent_no_double_write`
      and `test_check_in_via_qr_then_tracking_id_is_idempotent_no_double_write`
      as regression coverage for both directions — both now assert a 200
      idempotent no-op (unchanged `checkedInAt`) rather than the 409
      originally asserted, per the amendment in 2.1/3.3 above.

## 4. Documentation

- [x] 4.1 Update `docs/features/invitations.md` to describe the tracking-ID
      check-in endpoint's re-entry/cycling behavior, consistent with
      however the QR check-in/check-out cycling is already documented
      there.

## 5. Verification

- [x] 5.1 Reproduced the original bug live against the running dev server
      (not just via pytest) before fixing: confirmed a visitor checked in
      via `PATCH /api/v2/invitations/{trackingId}/check-in` could be checked
      in a second time via `PATCH /api/v2/invitations/qr/{token}/check-in`
      with no check-out in between (200, not 409) — root-caused to
      `check_in_if_eligible` never writing `check_in_status`. Re-ran the
      same live reproduction after the fix: now correctly 409s in both
      directions, and the checkout → re-entry cycle succeeds as intended.
- [x] 5.2 `ruff check` / `ruff format --check` clean on
      `src/vmss_api/invitations/`.
- [x] 5.3 `ddev exec uv run pytest src/vmss_api/invitations/tests.py
      src/vmss_api/approvals/tests.py` green — 316 passed.

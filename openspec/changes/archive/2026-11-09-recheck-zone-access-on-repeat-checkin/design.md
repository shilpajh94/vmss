## Context

`_check_in_resolved` (QR and code) in `invitations/checkin.py` returns early when `check_in_status == "checked_in"`. Zone enforcement (`enforce_checkin_zone`) sits only on the transition path after that return, so a repeat call never reaches it. `enforce_checkin_zone` already builds a visit snapshot "as it will stand after check-in", reads `effective_zone_ids` live, and handles denial (event, audit, alert, 403). See proposal.md for the motivation.

## Goals / Non-Goals

**Goals:**
- Reuse the existing zone decision on the already-checked-in path so the result reflects current allowed zones.
- Keep the idempotent no-op guarantees for the allowed case.

**Non-Goals:**
- No checkout on denial, no new response fields, no change to `/access/scan` or check-out.

## Decisions

1. **Call `enforce_checkin_zone` from the early-return branch, before returning the no-op.** One code path serves both endpoints. The tracking-ID path (`_perform_check_in`) has no zone check on first check-in, so it is left alone. Alternative: a separate "zone status" check function. Rejected: it duplicates decision, event and alert logic.
2. **Add a `record_allowed: bool` parameter to `enforce_checkin_zone` (default `True`; `False` on repeat calls).** An allowed repeat scan then writes no `entry` event, so the inside-by-zone report isn't double counted. A denied repeat scan still records the `denied` event, audit row and alert, which is the audit-relevant signal. The first-time path is unchanged.
3. **Denial leaves state untouched.** The early return stays before any `UPDATE`; only the denial commit (event + audit) happens. Visitor remains `checked_in`, which keeps "who's inside" accurate.
4. **Order of checks.** Device location (`_enforce_device_location`) stays first. The zone check then runs on the repeat path using the existing `today_local` computation, so it is moved or duplicated just ahead of the branch. Watchlist, expiry and the other first-time rules are NOT re-applied to a repeat call, preserving the documented "flag added after entry must not break repeat call" rule. `can_enter` still evaluates its own rules (including watchlist) as it does for a first-time zone check; a flagged visit will therefore show a zone denial from a single-zone device. Accepted: that is the correct access answer.
5. **Router audit.** `changed` stays `False` on an allowed repeat, so no `invitation_qr_checked_in` audit is written; the denial writes its own `zone_entry_denied` audit inside the gate.

## Risks / Trade-offs

- [A repeat scan that used to be 200 can now be 403] → only when zone access is on and the device is single-zone; documented in the feature docs.
- [Repeat scan adds a zone-rule query per call] → one extra `effective_zone_ids` and zone lookup, only when the toggle is on and a security device is present; bounded by the existing 20/min rate limit.
- [Denied repeat scans could spam Security alerts] → alert dedupe (`ZONE_DENIAL_ALERT_DEDUPE_SECONDS`) already applies.

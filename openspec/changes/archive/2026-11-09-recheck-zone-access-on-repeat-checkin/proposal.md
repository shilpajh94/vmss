## Why

Check-in is meant to show the visitor's zone access as it stands now. Today it doesn't. When a visitor is already `checked_in` and reception then changes their allowed zones, every later scan of the QR (`PATCH /api/v2/invitations/qr/{token}/check-in`) or SMS code (`PATCH /api/v2/invitations/code/check-in`) returns the same "Verification passed" with no zone decision. The zone rule is only applied on the first `unused`/`checked_out` -> `checked_in` transition, so updated zone access takes effect only after a check-out and a fresh check-in.

## What Changes

- A repeat check-in call on an already `checked_in` visit, made from a security device linked to exactly one zone (with `zone_access_enabled` on), re-runs the zone decision against the visit's **current** allowed zones instead of returning a blanket pass.
  - Allowed: 200 "Verification passed", unchanged data, no state change.
  - Denied: 403 `Zone entry denied` with the stable deny `reason`, a `denied` zone event, the audit row and the Security alert, exactly as a first-time denial. The visit stays `checked_in`.
- This covers the QR-token and check-in-code endpoints. The tracking-ID check-in is unchanged: it never applies zone rules on first check-in, so a repeat-only check would be inconsistent.
- Nothing else about the idempotent no-op changes: no new `checkedInAt`, no host notification, no check-in audit entry.
- Out of scope: a new endpoint, a response field listing zones, and changes to check-out or the `/access/scan` gate endpoint.

## Capabilities

### New Capabilities
<!-- none -->

### Modified Capabilities
- `zone-access-control`: adds a requirement that a repeat check-in on an already checked-in visit re-evaluates zone access. The base capability is introduced by the unarchived change `add-zone-access-control`, so this delta is ADDED on top of it. Archive/sync that change first.

## Impact

- Code: `src/vmss_api/invitations/checkin.py` (`_check_in_resolved`), `src/vmss_api/access_control/checkin_gate.py` (`enforce_checkin_zone`, currently assumes a not-yet-checked-in visit), the check-in route docstrings in `invitations/router.py`.
- API: a repeat check-in can now return 403 where it returned 200. This is only reachable when zone access is enabled and the device is tied to a single zone, so it is additive for tenants with the toggle off.
- Tests: `access_control` and `invitations` check-in tests.
- Docs: `docs/features/access_control.md`, `docs/features/invitations.md`.

## Assumptions (change if wrong)

- The request was garbled. Read as: a visitor already checked in, whose zone access was then updated, still gets "access granted" on every check-in call. It should reflect the current access level, and not only after a check-out.
- A denied repeat scan does **not** check the visitor out. It only refuses that scan.
- An allowed repeat scan writes no new `entry` event, so the inside-by-zone report isn't double counted.
- Requests with no device, a non-security device, or a device on zero or several zones are unaffected, as today.

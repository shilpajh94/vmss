## 1. Configuration

- [x] 1.1 Add a `qr_token_encryption_key` (or equivalent) setting to
      `core/config.py`, sourced from `.env`.
- [x] 1.2 Add the corresponding placeholder entry to `.env.example`.

## 2. Data Model & Migration

- [x] 2.1 Add `InvitationQRCode` model to `invitations/models.py`:
      `invitation_id` (FK, unique), `qr_token`, `image_storage_key`,
      `TimestampMixin`.
- [x] 2.2 Add `check_in_status` column to `Invitation`
      (`String`, default `"unused"`), kept parallel to the existing
      `status` column — do not touch any existing `status` transition.
- [x] 2.3 Author the `alembic_tenant` migration for the new table and
      column, with a backfill default of `unused` for existing rows.
- [x] 2.4 Verify the migration applies cleanly via the existing
      provisioning/upgrade-all-tenants path against the `vmss_test`
      database. (Verified via ddev against `tenant_default` — upgrade,
      downgrade, and re-upgrade all applied cleanly.)

## 3. Token Encryption

- [x] 3.1 Add `invitations/qr_token.py` with
      `encrypt_invitation_token(invitation_id) -> str` and
      `decrypt_invitation_token(token) -> uuid.UUID | None`, mirroring
      `core/encryption.py`'s Fernet-based pattern (`lru_cache`d `Fernet`
      instance, a not-configured error when the key is unset) but keyed by
      its own dedicated `settings.qr_token_encryption_key` — not the
      existing `sso_encryption_key`.
- [x] 3.2 Unit-style tests for the token module: round-trip
      encrypt/decrypt, a tampered/modified token is rejected
      (`InvalidToken`), a malformed input is rejected — all without
      touching the database (per `testing-standards.md` §3, these can call
      the module directly).

## 4. QR Generation at Approval

- [x] 4.1 Add a repository method to create/update an invitation's
      `InvitationQRCode` row.
- [x] 4.2 Generate the encrypted token once, render the QR PNG, persist
      the image via `core/storage.py::save`, and persist the
      `InvitationQRCode` row — implemented as `service.py::_issue_qr_code`,
      called from `create_invitation` (auto-approved path) and
      `approve_invitation` (manual path) rather than inside the Celery
      task, since both already hold a real tenant-bound session at the
      moment of approval; the task itself now takes the already-issued
      `qr_token` as an explicit argument instead of deriving it (see
      design.md's Fernet-reuse decision and tasks.py's updated docstring).
- [x] 4.3 `_issue_qr_code` is get-or-create (checks for an existing row
      first), so any future resend/reprint call reuses the persisted
      token/image instead of regenerating — verified via badge issuance
      and reprint (4.4), which call the same helper.
- [x] 4.4 Updated `invitations/badge.py::render_badge_png` to take an
      explicit `qr_token` and encode that (not `tracking_id`) in the
      embedded QR; `service.py::issue_badge`/`reprint_badge` now call
      `_issue_qr_code` to source it, so the badge and the emailed QR
      always encode the same token.

## 5. Check-In State Machine

- [x] 5.1 Add a repository method that, given a decrypted `invitation_id`,
      atomically applies the `unused`→`checked_in` or
      `checked_in`→`checked_out` transition to `check_in_status`
      (single conditional `UPDATE`, matching the existing
      `check_in_if_eligible` pattern for race-safety), and mirrors the
      same transition into the existing `status` column in the same
      statement/transaction.
- [x] 5.2 Add a service method
      `check_in_by_qr_token(tenant_db, token, *, tenant)` that: decrypts
      the token (400 on failure); loads the invitation; rejects if
      `status != "approved"` (400) or `watchlist_flagged` (existing block
      behavior); on `unused`, rejects if `expires_at` has passed (410),
      otherwise transitions to `checked_in`; on `checked_in`, transitions
      to `checked_out` with no expiry check; on `checked_out`, rejects as
      already completed (409).
- [x] 5.3 Reuse the existing host-push-notification trigger for
      checked-in/checked-out events so the QR path satisfies the existing
      "Invitation Approval, Denial, Reschedule, Check-In, and Check-Out
      Notify the Host via Push" requirement without a separate
      implementation.

## 6. API Endpoint & Schema

- [x] 6.1 Expand the check-in response schema (new or extended
      `InvitationOut`/`InvitationCheckInOut` in `invitations/schemas.py`)
      to include visitor contact, resolved host display name, purpose of
      visit, department, `submittedAt`/`approvedAt`/`checkedInAt`/
      `checkedOutAt`, `expiresAt`, and `checkInStatus`.
- [x] 6.2 Add `PATCH /api/v2/invitations/qr/{token}/check-in` to
      `router_v2` in `invitations/router.py`: public, same rate limit as
      the existing tracking-ID route, `Idempotency-Key` header support
      matching the existing pattern, `response_model=Envelope[...]` per
      `api-documentation.md` §1.
- [x] 6.3 Map service-layer rejections to the response/error matrix from
      the confirmed frontend spec: invalid token → 400, not approved →
      400, expired-on-entry → 410, already-completed → 409, success → 200
      with the appropriate "Verification passed" / "Checked out
      successfully" message.

## 7. Audit & Observability

- [x] 7.1 Extend the existing `record_audit_log` background-task calls to
      cover QR-driven check-in and check-out (new `entity_type`/`action`
      values consistent with the existing `invitation_checked_in_public`
      naming).
- [x] 7.2 Log a `WARNING`-level structlog line (not an audit entry — this
      isn't a mutation) for a rejected/tampered token scan, per
      `logging-observability.md` §3 and `security-architecture.md` §5's
      "security events... logged at WARNING."

## 8. Tests

- [x] 8.1 Endpoint test: full happy path — approve an invitation, scan
      to check in, scan again to check out, third scan returns 409.
      (`test_qr_check_in_full_lifecycle`)
- [x] 8.2 Endpoint test: entry scan after `expires_at` returns 410;
      exit scan after `expires_at` (while `checked_in`) still succeeds.
      (`test_qr_check_in_entry_after_expiry_rejected`,
      `test_qr_check_in_exit_after_expiry_still_succeeds`)
- [x] 8.3 Endpoint test: tampered token returns 400 without leaking which
      invitation it targeted. (`test_qr_check_in_tampered_token_rejected`,
      `test_qr_check_in_valid_token_unknown_invitation_rejected`)
- [x] 8.4 Endpoint test: watchlist-flagged invitation is blocked on the
      QR path the same way it already is on the tracking-ID path.
      (`test_qr_check_in_watchlist_flagged_blocked`)
- [x] 8.5 Endpoint test: not-yet-approved (`submitted`) invitation's token
      (if one exists) is rejected — QR tokens are only issued at
      approval, so this mainly guards the "no QR before approval"
      invariant from `4. QR Generation at Approval`.
      (`test_qr_check_in_not_yet_approved_rejected`)
- [x] 8.6 Tenant-isolation test per `testing-standards.md` §2, using the
      `make_tenant_schema`/`open_tenant_session` fixtures, scaffolded even
      though this release's token payload doesn't carry a tenant claim
      (per design.md's confirmed Non-Goal).
      (`test_qr_check_in_repository_tenant_schema_isolation`)
- [x] 8.7 Idempotency test: a retried request with the same
      `Idempotency-Key` returns the cached response rather than advancing
      `check_in_status` a second time. (`test_qr_check_in_idempotency_key_replay`)
- [x] 8.8 (added) Token-module unit tests (round-trip, tampered, malformed,
      not-configured), rate-limit trip, audit-entry write, and an
      approval-flow test confirming the persisted `InvitationQRCode.qr_token`
      is exactly what's handed to the notification task.

## 9. Documentation

- [x] 9.1 Update `docs/features/invitations.md` with the new endpoint,
      the `check_in_status` lifecycle, and the expiry-on-entry-only rule.

## 10. Correction: cycling lifecycle (checked_out is not terminal)

The original design/implementation treated `checked_out` as a dead end (a
third scan rejected 409). Corrected per design.md's new "checkInStatus
cycles indefinitely" decision — a visitor may have multiple entry points
during one visit.

- [x] 10.1 `repository.py::check_in_by_qr_if_eligible`: broaden the
      eligibility condition from `check_in_status == "unused"` to
      `check_in_status.in_(("unused", "checked_out"))`, keeping the
      `status == "approved"`, `watchlist_flagged.is_(False)`, and
      `expires_at > now()` conditions unchanged.
- [x] 10.2 `service.py::check_in_by_qr_token`: remove the `elif
      check_in_status == "checked_out": raise 409` branch entirely — with
      10.1 in place, every `check_in_status` value maps to exactly one
      transition, so there is no remaining state to reject.
- [x] 10.3 Rewrite `invitations/tests.py::test_qr_check_in_full_lifecycle`'s
      final assertion (currently: third scan → 409) into a re-entry
      assertion (third scan → 200, `checkInStatus` back to `checked_in`),
      and add a further scan back to `checked_out` to demonstrate a full
      second cycle.
- [x] 10.4 New test: a re-entry scan (`checked_out` → `checked_in`) after
      `expires_at` has passed is rejected 410, mirroring the existing
      first-entry-after-expiry test.
- [x] 10.5 Re-update `docs/features/invitations.md`'s QR check-in section
      to describe the cycling lifecycle instead of the one-round-trip
      version.
- [ ] 10.6 (flagging only, not a code task) The shared frontend
      requirement artifact published earlier in this project states "a
      third scan is rejected" — that page should be corrected and
      republished once this fix ships, since it's an external document
      this OpenSpec change doesn't track.

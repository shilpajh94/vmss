## 1. Test-Infrastructure: Corrected Diagnosis (no code change)

- [x] 1.1 ~~Add a test-only session seam to `conftest.py`~~ — **not
      implemented**. Re-verification (group 3 below) showed the suite is
      already deterministic under serial execution; the originally-suspected
      background-write/session-handling bug doesn't reproduce (design.md
      Decision 1). No change made to `conftest.py`.
- [x] 1.2 ~~Generalize the Celery eager-mode session workaround~~ — **not
      needed**, same finding as 1.1.
- [x] 1.3 Confirmed `auth/audit.py::record_audit_log`'s production code path is
      unaffected — it was never touched, consistent with the corrected finding.

## 2. Test-Infrastructure: Teardown Ordering (no code change)

- [x] 2.1 ~~Reorder `db_session` teardown deletes~~ — **not implemented**. The
      `StaleDataError`/orphaned-row symptoms that motivated this task were
      artifacts of running multiple `pytest` processes concurrently during the
      original audit, not a defect in the teardown's delete order under normal
      (serial) execution (design.md Decision 1, Non-Goals).
- [x] 2.2 Confirmed no orphaned rows remain in global-schema tables (`tenants`,
      `tenant_user_index`, `permissions`) after serial `platform`/`reports`
      test runs — table queried directly post-run, empty as expected.

## 3. Verify Test Determinism

- [x] 3.1 Ran `ddev exec uv run pytest src/vmss_api/auth/tests.py -q` standalone
      5 times against the real `vmss_test` database: 18 passed every time,
      zero flakes.
- [x] 3.2 Repeated for `src/vmss_api/org_structure/tests.py` (3×, 70 passed
      each), `src/vmss_api/platform/tests.py` (2×, 6 passed each),
      `src/vmss_api/reports/tests.py` (2×, 3 passed each), and
      `src/vmss_api/invitations/tests.py` (3×, 24 passed each) — all green,
      every run.
- [x] 3.3 Ran the full suite (`ddev exec uv run pytest`) twice in a row: 156
      passed both times, identical result (spec.md "Full suite run is reliably
      green" — confirmed satisfied by current code, no change needed). Also
      ran `platform`+`reports`+`auth` concurrently as a control: reproduced the
      original failure signatures immediately, confirming the corrected
      diagnosis (concurrent-process collision on shared global-schema rows,
      not a per-request session bug).

## 4. Invitation Creation Idempotency (API-09)

- [x] 4.1 Added an optional `Idempotency-Key` header parameter to
      `invitations/router.py::create_invitation`, reusing the existing
      `_cached_response`/`_cache_response` helpers already implemented for the
      self-registration endpoint in the same file (design.md Decision 2).
- [x] 4.2 Cache key: `vmss:{tenant_id}:invitations:idempotency:{key}`, 24h TTL
      — unchanged, reused the constant/helper already keyed this way.
- [x] 4.3 Added `test_create_invitation_idempotency_key_replay` (same key
      replayed → one invitation, identical response bodies) and
      `test_create_invitation_without_idempotency_key_creates_separately`
      (no header → two independent invitations, current/unchanged behavior) to
      `invitations/tests.py`. Cache-window-expiry scenario not separately
      tested — same as the pre-existing `test_self_register_idempotency_key_replay`
      pattern this mirrors, which also doesn't fake Redis TTL expiry.

## 5. Track Endpoint Response Contract (API-12)

- [x] 5.1 Changed `GET /invitations/track`'s `response_model` in
      `invitations/router.py` from `Envelope[InvitationTrackingOut]` to
      `Envelope[InvitationTrackingOut | list[InvitationTrackingSummaryOut]]`
      (design.md Decision 3) — no change to either lookup branch's actual
      return value.
- [x] 5.2 Confirmed via `app.openapi()`: the endpoint's 200 response schema is
      now `anyOf: [InvitationTrackingOut, array[InvitationTrackingSummaryOut]]`
      — both real shapes documented.
- [x] 5.3 Found `test_track_by_email_minimal_disclosure` (already existing)
      already asserts `set(body[0].keys()) == {"trackingId", "status"}` for
      the email-lookup branch — this already closes the gap the audit found;
      no new test needed.

## 6. Final Verification

- [x] 6.1 `ddev exec uv run ruff check` and `ddev exec uv run ruff format --check`
      clean on `src/vmss_api/invitations/` (no `conftest.py` changes were made,
      per the corrected group 1/2 findings).
- [x] 6.2 `ddev exec uv run mypy src/vmss_api/invitations` — success, no issues
      (11 files).
- [x] 6.3 Full `ddev exec uv run pytest` — 158 passed (156 + 2 new idempotency
      tests), per `git-workflow.md` §4's merge gate.
- [x] 6.4 Updated `docs/features/invitations.md` to document the
      `Idempotency-Key` header on invitation creation and the track endpoint's
      two response shapes.

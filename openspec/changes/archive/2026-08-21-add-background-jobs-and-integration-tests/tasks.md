## 1. Shared Email-Sending Primitive

- [x] 1.1 Create `core/emailing.py`: move `EmailSender` protocol, `Attachment`
      protocol/`_Attachment`/`make_attachment`, and `SmtpEmailSender` out of
      `invitations/notifications.py` verbatim (no logic changes).
- [x] 1.2 Update `invitations/notifications.py` to import
      `EmailSender`/`SmtpEmailSender`/attachment helpers from
      `core/emailing.py`; keep `SmsSender`, `UnconfiguredSmsSender`,
      `SmsGatewayNotConfiguredError`, and the module-level `email_sender`/
      `sms_sender` instances there (invitation-specific, SMS not needed by
      reports).
- [x] 1.3 Run `invitations/tests.py`'s existing email-dispatch tests
      unmodified to confirm the extraction is behavior-preserving.

## 2. Celery Beat Infrastructure

- [x] 2.1 Add `celery_app.conf.beat_schedule` entry
      `"dispatch-daily-rollup-snapshots"` in `core/celery_app.py`, wired to
      `reports.tasks.dispatch_daily_rollup_snapshots` on
      `crontab(hour=2, minute=0)`.
- [x] 2.2 Extend `celery_app.autodiscover_tasks([...])` to include
      `vmss_api.reports`.
- [x] 2.3 Add a `vmss-api-celery-beat` entry to `.ddev/config.yaml`'s
      `web_extra_daemons`, running
      `uv run celery -A vmss_api.core.celery_app:celery_app beat --loglevel=info`,
      sibling to the existing `vmss-api-celery-worker` daemon.
- [x] 2.4 Document the beat daemon prerequisite in `README.md` next to the
      existing Celery worker note (`add-celery-worker-and-demo-seed-script`).

## 3. Reports Scheduled Snapshot Job

- [x] 3.1 Add an Admin-role recipient query to `reports/repository.py`
      (following the existing precedent of `BranchRollupRepository`
      importing `vmss_api.auth.models.User` directly): return every
      tenant-scoped `User` holding the `"admin"` role.
- [x] 3.2 Create `reports/tasks.py`:
      - `dispatch_daily_rollup_snapshots` (beat-triggered, no args): lists
        active tenants (global schema) and calls
        `send_tenant_rollup_snapshot.delay(tenant_id=..., tenant_schema=...)`
        per tenant.
      - `send_tenant_rollup_snapshot(tenant_id, tenant_schema)`: Redis
        `SET NX EX` idempotency guard on
        `vmss:{tenant_id}:reports:snapshot-sent:{utc_date}` (26h TTL);
        resolves the tenant session, calls the existing
        `service.get_cross_branch_rollup`, resolves Admin recipients via
        3.1, and sends one summary email per recipient via
        `core/emailing.py`'s `SmtpEmailSender`. Logs `INFO` (not `ERROR`)
        when a tenant has zero Admin recipients. Declares
        `autoretry_for`/`retry_backoff`/`max_retries` and logs `ERROR` with
        `tenant_id` context on retry exhaustion, per the `background-jobs`
        spec.
- [x] 3.3 Bind `request_id`/tenant context into `structlog` at the top of
      both task bodies (no real request here — use a generated/task-id
      correlation value, consistent with `logging-observability.md` §1's
      intent for traceability).

## 4. `background-jobs` Capability Tests

- [x] 4.1 `reports/tests.py`: scheduled task computes the same totals
      `get_cross_branch_rollup` would return for the same tenant state
      (spec: "Snapshot content matches the on-demand rollup").
- [x] 4.2 `reports/tests.py`: only Admin-role users receive the email; a
      non-admin user in the same tenant does not (spec: "reaches every
      tenant admin and no one else").
- [x] 4.3 `reports/tests.py`: a redelivered/re-executed
      `send_tenant_rollup_snapshot` call for the same tenant+date does not
      send a second email (Redis idempotency guard).
- [x] 4.4 `reports/tests.py`: `dispatch_daily_rollup_snapshots` with one
      tenant's `send_tenant_rollup_snapshot` raising still dispatches (and,
      in a worker, still processes) every other active tenant.
- [x] 4.5 `reports/tests.py`: retry-exhaustion path logs `ERROR` with
      `tenant_id` context, mirroring
      `invitations/tests.py::test_send_visit_confirmation_exhausted_retries_logs_error`.
- [x] 4.6 `reports/tests.py`: a tenant with zero Admin-role users logs
      `INFO` and sends no email, without raising.

## 5. API-18 Integration-Test Gap Audit

- [x] 5.1 Re-read `testing-standards.md` §2 against current coverage in
      `invitations/tests.py`, `registrations/tests.py`, and
      `tests/test_workflow_visitor.py`; list any endpoint/scenario combo
      (happy path, permission-denied, tenant-isolation) not already
      covered by the three prior test-focused changes
      (`complete-api-test-coverage`, `add-end-to-end-workflow-tests`,
      `close-api-test-coverage-gaps`).

      **Finding**: every endpoint in both routers has all three required
      cases. `invitations`: `POST /invitations` (happy path × individual/
      group, `test_create_invitation_requires_permission` 403,
      `test_invitation_repository_tenant_schema_isolation`), `GET
      /invitations` (happy path + filters/sort,
      `test_list_invitations_requires_permission` 403 +
      `test_list_invitations_unauthorized_branch_id_rejected`,
      `test_invitation_list_page_tenant_schema_isolation`), `GET
      /invitations/track` (happy path × tracking-id/email; no permission
      check to test since it's public; tenant-isolation is structurally
      untestable here — `invitations/deps.py`'s `track_default_tenant_db`
      always resolves the single `default_tenant_slug` schema, a
      documented single-tenant limitation, not a bug this change
      introduces or should silently paper over with a fabricated test).
      `registrations`: `POST /registrations/walk-in` (happy path ×
      individual/group; the device-key-auth trio — missing/invalid/
      inactive key, all 401 — stands in for "permission-denied" since
      this endpoint has no RBAC to deny, `registrations/tests.py`'s own
      comments already label it that way;
      `test_walk_in_registration_tenant_schema_isolation`). No status-code
      or assertion inconsistencies found.
- [x] 5.2 No genuine gap found in 5.1 — nothing to add.
- [x] 5.3 Recorded above: the only near-gap (`GET /invitations/track`'s
      tenant-isolation case) is a structural, already-documented
      single-tenant-routing limitation, not an oversight, and is left
      untested rather than covered with a test that couldn't actually
      exercise cross-tenant isolation.

## 6. Documentation

- [x] 6.1 Add `docs/features/background-jobs.md`: purpose, the beat
      schedule, the dispatcher/per-tenant task split, the idempotency
      Redis key, and how to add a future scheduled task.
- [x] 6.2 Update `docs/features/reports.md` (or create it if it doesn't
      exist yet) with the new scheduled-snapshot behavior alongside the
      existing on-demand endpoint.

## 7. Verification

- [x] 7.1 `ruff check` and `ruff format --check` clean.
- [x] 7.2 `mypy` clean on any touched module under `core/` (strict-typing
      scope per `project-rules.md`).
- [x] 7.3 Full `pytest` suite green, including the new `background-jobs`/
      `reports` task tests and any tests added in Section 5.

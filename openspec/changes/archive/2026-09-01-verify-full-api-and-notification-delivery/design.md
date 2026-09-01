## Context

See `proposal.md` — Why for the four concrete findings motivating this pass
(dual-channel gap, single-Mailpit-test gap, the currently-failing
cross-tenant test, the open OTP/SMTP dev-delivery item).

This design extends, rather than re-derives, the workflow-ordered matrices
already built by the four prior audits:
`openspec/changes/codebase-review-and-e2e-scenario-test/` (route-vs-workflow
coverage + 3 fixed races + `test_workflow_full_lifecycle.py`) and
`openspec/changes/verify-sso-and-full-api-suite/` (API-01..API-19 stage
matrix, `design.md`'s Stages 1-8). Current baseline as of this design
(`ddev exec uv run pytest -q`): **605 passed, 1 failed** — up from the prior
audit's 358, reflecting the uncommitted approvals/invitations/notifications
work already in the tree (`git status`) plus other work merged since.

Read directly (not assumed from names) before writing this design:
`src/vmss_api/notifications/{service,tests}.py` (16 tests, including
`test_device_token_tenant_isolation`, `test_notify_step_approver_*`),
`src/vmss_api/invitations/tests.py`'s push-notification block (lines
~3006-3350: `test_create_invitation_submission_notifies_host_step_approver`
through `test_check_out_invitation_notifies_host`), and
`src/vmss_api/identity_verification/tests.py`'s OTP email/SMS tests.

## Goals / Non-Goals

**Goals:**
- Prove, per real HTTP request, that both the visitor-facing channel
  (email/SMS) and the staff-facing channel (push) actually fire correctly
  together — not each proven in a separate test that silences the other.
- Raise OTP-over-email, denial, and reschedule notifications to the same
  real-SMTP-round-trip (Mailpit) evidence bar the approval notification
  already has, prioritizing OTP given its live-incident history.
- Root-cause and close the one currently-failing test
  (`test_create_invitation_cross_tenant_visitor_category_id_rejected`).
- Re-confirm (not re-derive) the API-01..API-19 matrix plus SSO is still
  green, and add the one stage it never had: Notifications (push).
- End with a green full suite, clean `ruff`/`mypy`, and a closing summary
  that states the OTP/SMTP dev-delivery item's status plainly.

**Non-Goals:**
- Not re-deriving the full API-01..API-19 stage-by-stage matrix from
  scratch — `verify-sso-and-full-api-suite/design.md` already did that in
  detail 8 days ago (2026-08-24) and it was fully applied (all 358 tests
  passing then). This pass spot-re-confirms those stages via a full suite
  run and named-regression-test check, the same "re-confirm without
  re-deriving" approach that audit itself used for its own prior stages.
- Not attempting the OTP/SMTP dev-server verification itself (no network
  route to `vmss-dev.mypits.org` or its logs from this environment,
  confirmed by two prior changes) — covered as a stated-plainly follow-up,
  not a task this change can complete.
- Not archiving the four prior changes this supersedes — flagged in the
  closing summary as a follow-up action, since archiving is a separate
  workflow step, not part of implementing this change's own tasks.
- Not building a general dual-channel test helper/fixture unless the
  per-event test bodies turn out to need one to stay readable — decide at
  apply time from the actual diff size, not speculatively up front.

## Decisions

### Stage 9 — Notifications (push), inserted after Invitations/Approvals

| # | Area | Current state | This pass |
|---|---|---|---|
| N1 | `POST /notifications/devices` | `test_register_device_success`, `_requires_auth`, `_re_registration_updates_existing_row`, `_reassigns_token_from_previous_owner` — covered. | Re-confirm only. |
| N2 | `DELETE /notifications/devices/{fcmToken}` | `test_unregister_device_success`/`_requires_auth`/`_unknown_device_is_not_an_error`/`_owned_by_another_user_is_a_no_op` — covered. | Re-confirm only. |
| N3 | Tenant isolation | `test_device_token_tenant_isolation` — covered (repository-level, matching `auth/tests.py`'s reference pattern). | Re-confirm only — proposal.md's initial read of this as "absent" was wrong; corrected before writing this design. |
| N4 | `notify_step_approver` role resolution | `test_notify_step_approver_admin_role_sends_no_push`, `_non_admin_role_dispatches`, `_unresolvable_role_dispatches` — covered. | Re-confirm only. |
| N5 | `send_push` task | `test_send_push_skips_recipient_with_no_registered_device`, `_delivers_to_every_registered_device`, `_deletes_device_reported_as_unregistered`, `_exhausted_retries_logs_error` — covered. | Re-confirm only. |
| N6 | Per-event recipient/payload (invitations) | 9 tests in `invitations/tests.py` (submission host/role/admin-exclusion/auto-approve-skip/hostless-skip, approve/deny/reschedule/check-in/check-out notifies-host) — covered for the push side only. | **Gap to close (Decision 2 below).** |
| N7 | Per-event recipient (approvals) | `approvals/tests.py` has its own `_fake_notify_user`/`_fake_notify_role_at_branch`/`_fake_notify_step_approver` coverage around `approve_step`/`_activate_next_step` (≈4 call sites, lines 361-518). | Re-confirm only. |

Net: Stage 9 is overwhelmingly already covered — this is a narrower stage
than the SSO one `verify-sso-and-full-api-suite` had to build from a 4-gap
starting point. The one real content gap is N6, addressed as its own
decision since it's shared with the email-side work below.

### Decision 1 — Mailpit-backed real-delivery tests for OTP, denial, reschedule

`test_send_approval_notification_delivers_email_with_qr_via_mailpit`
(`invitations/tests.py:1416`) is the template: leave `notifications.email_sender`
as the real `SmtpEmailSender` (instead of monkeypatching it to a stub), let
the Celery task run, then poll Mailpit's REST API (`localhost:8025/api/v1`,
already reachable in the ddev environment — no new infra) for a message
matching a unique tracking value, and assert subject/recipient/body-relevant
content against the *received* message.

Apply the same pattern to:
- **OTP request over email** (`identity_verification/tests.py`, alongside
  `test_request_and_verify_otp_over_email_success`) — highest priority per
  proposal.md finding #2. Assert the Mailpit message's subject is
  "Your verification code" and that the code embedded in its body
  round-trips through `/otp/verify` successfully, i.e. this becomes a
  request-and-verify test using a real received email's code, not the
  in-process stub's captured `body` string.
- **Denial notification** (`invitations/tests.py`, alongside
  `test_deny_invitation_notifies_host`) and **reschedule notification**
  (alongside `test_reschedule_invitation_notifies_host`) — same pattern,
  asserting each event's distinct subject line actually arrives.

**Alternative considered**: keep every test on the stub and add exactly one
new Mailpit test per channel as a separate file (`test_email_delivery.py`).
Rejected — colocating the Mailpit variant next to each event's existing
stub-based test (same fixture setup, same invitation-building helpers) is
less duplication than a parallel file re-deriving the same setup, and
matches where `test_send_approval_notification_delivers_email_with_qr_via_
mailpit` already lives.

**Cost/flakiness note**: a real SMTP round-trip through Mailpit is slower
and has more moving parts (a running Mailpit container, network I/O) than a
stub assertion. This is accepted for the reason in proposal.md finding #2 —
these are exactly the events (especially OTP) where "the stub was called
correctly" has already once diverged from "an email genuinely arrived" in
production. Keep the *existing* stub-based tests too (they're cheap and
catch payload-content regressions fast); Mailpit tests are additive, not a
replacement.

### Decision 2 — Dual-channel assertion for invitation lifecycle events

For each of `test_approve_invitation_notifies_host`,
`test_deny_invitation_notifies_host`, `test_reschedule_invitation_notifies_
host`, `test_check_in_invitation_notifies_host`,
`test_check_out_invitation_notifies_host`, and
`test_create_invitation_submission_notifies_host_step_approver`: replace the
event's `monkeypatch.setattr(tasks.send_X_notification, "delay", lambda
**kw: None)` with `lambda **kw: calls_email.append(kw)` (mirroring the
existing pattern already used for the push side), and add an assertion on
`calls_email[0]` (recipient/tracking id) alongside the existing push
assertion. This is a small, mechanical change to tests that already exist —
no new fixtures, no new test files, since the harness (client, host,
invitation builder) is already there.

**Alternative considered**: a single new end-to-end test per event
asserting both channels, leaving the existing tests untouched. Rejected —
that duplicates the existing test's entire setup for a check that belongs
inside it; extending in place is smaller and keeps one source of truth per
event's push-and-email behavior.

### Decision 3 — Root-causing the cross-tenant visitor-category failure

`test_create_invitation_cross_tenant_visitor_category_id_rejected` fails
with a `UniqueViolationError` on `visitor_categories_name_key` for
`(name)=(Other Tenant Category)` in schema `tenant_other_category_test`.
Two candidate root causes to check, in order, before picking a fix:
1. **Stale data from a prior run**: if `tenant_other_category_test` is a
   schema name reused across test sessions without being dropped/recreated,
   and some other test inserts a `VisitorCategory` named "Other Tenant
   Category" into it without cleanup, the second run's insert collides.
   Fix: scope the fixture that creates this row to a properly
   torn-down/unique schema, or `make_tenant_schema`'s own teardown, matching
   how other cross-tenant tests in this suite already isolate their schema
   names.
2. **A second test using the identical category name in the identical
   schema**: `grep -rn "Other Tenant Category"` across `tests.py` files to
   find a second definition; if found, rename one to a unique value (the
   established fix pattern for accidental name collisions in this suite,
   per `visitor_categories`' own `name` uniqueness being intentional
   per-schema, not a bug in the constraint itself).
- **Explicitly not assumed without checking**: that the unique constraint
  itself is wrong (e.g., should be scoped by something else). Under
  schema-per-tenant, `visitor_categories.name` unique *within one schema* is
  correct; a genuine cross-schema leak (the same connection somehow writing
  into the wrong schema) would be a much more serious finding and is
  checked for explicitly (Decision 3, step 1's "reused schema name" case)
  before assuming it's just test hygiene.

### Decision 4 — Notification module in `mypy`'s strict scope for this pass

`notifications/` is untracked and new; run `mypy` on it explicitly this
pass (not deferred to "incremental" per `project-rules.md`'s general
relax-incrementally allowance) since it's cross-user dispatch code handling
device tokens and FCM payloads — the same reasoning `project-rules.md`
already applies to `core`/money/PII/auth modules.

## Risks / Trade-offs

- **[Risk] Mailpit tests are environment-dependent** (require the Mailpit
  container reachable at `localhost:8025`, already true for the one
  existing test) **→ Mitigation**: no new infra requirement — same
  dependency the approval-notification test already has; if Mailpit isn't
  running, that one existing test would already be failing, which is a
  pre-condition check, not a new fragility this change introduces.
- **[Risk] The cross-tenant test's root cause could turn out to be a real
  tenant-schema leak, not test hygiene** — a materially bigger finding than
  this change is scoped to fix inline → **Mitigation**: Decision 3 checks
  for this explicitly first; if confirmed, stop and report per the
  stop-and-report threshold rather than patching the symptom.
- **[Risk] Extending 6 existing tests' monkeypatch targets (Decision 2)
  could silently drop the exact assertion each already had** →
  **Mitigation**: extend in place (add an email-capture list and assertion
  alongside the existing push one), never delete/rewrite the existing push
  assertion.

## Migration Plan

Not applicable — this is a test-and-fix change with no schema/deployment
migration beyond confirming the already-authored
`alembic_tenant/versions/6f4e364ea9c8_device_tokens.py` applies cleanly
(covered as a task, not a new migration).

## Why

The user asked for a full pass confirming every API works, every email
actually sends/receives, and every notification actually arrives, across
all workflow scenarios. Four concrete reasons this is due now, not a
restatement of the four prior "verify everything" changes already sitting
planned-but-unarchived in this repo (`verify-sso-and-full-api-suite`,
`codebase-review-and-e2e-scenario-test`, `diagnose-otp-email-delivery-
failure`, `verify-email-fix-and-run-tests`):

1. **The entire push-notification feature is uncommitted and never audited
   end-to-end.** `src/vmss_api/notifications/` (device registration + FCM
   dispatch, 16 tests, including its own tenant-isolation test) plus
   `src/vmss_api/invitations/push_notifications.py` and the tenant migration
   `alembic_tenant/versions/6f4e364ea9c8_device_tokens.py` are all untracked.
   The wiring that calls it — `invitations/service.py` (submit, approve,
   deny, reschedule, check-in, check-out) and `approvals/service.py`
   (`_activate_next_step`) — is modified-but-uncommitted on top of that.
   Per-event push recipient/payload assertions already exist for each of
   these (`invitations/tests.py`'s `test_*_notifies_host` /
   `test_create_invitation_*_notifies_role` series), but **every one of
   those HTTP-level tests stubs the event's email/SMS dispatch to a bare
   `lambda **kw: None`** while it captures the push call — so no test proves
   both channels fire correctly *for the same real request*, which is
   exactly the "emails... and notifications... receiving properly" claim
   the user wants confidence in together, not each channel proven in
   isolation. None of the four prior audits could have caught this gap:
   `codebase-review-and-e2e-scenario-test` and `verify-sso-and-full-api-
   suite` both predate the push feature existing at all.
2. **Only one of the several email-sending events has a test that proves an
   email is actually deliverable, not just that the code called a sender.**
   `invitations/tests.py::test_send_approval_notification_delivers_email_
   with_qr_via_mailpit` is the only test in the repo that lets a real
   `SmtpEmailSender.send` go out and then reads it back from Mailpit (the
   dev SMTP capture service) — subject, recipient, and QR attachment all
   verified against a real received message. Every other email-triggering
   path — denial notification, reschedule notification, and, notably,
   **OTP request/verify over email** (`identity_verification/tests.py::
   test_request_and_verify_otp_over_email_success`) — swaps in a recording
   stub (`_RecordingSender`) instead and only asserts the stub was called
   with the right subject/body. That is exactly backwards from a risk
   perspective: OTP-over-email is the one channel with an actual live
   dev-server failure history (`diagnose-otp-email-delivery-failure`), yet
   it is the least-proven of the three by this repo's own strongest
   evidence standard (Mailpit), which currently only covers the
   least-troubled path (approval).
3. **A fresh full-suite run right now already surfaces a real, reproducible
   failure**, not a hypothetical one: `ddev exec uv run pytest -q` —
   **605 passed, 1 failed** —
   `invitations/tests.py::test_create_invitation_cross_tenant_visitor_
   category_id_rejected` fails with `IntegrityError: duplicate key value
   violates unique constraint "visitor_categories_name_key"` on schema
   `tenant_other_category_test` (`(name)=(Other Tenant Category) already
   exists`). This is exactly the tenant-isolation class of test
   `testing-standards.md` §2 requires and treats as load-bearing, and it is
   currently red on a test whose own name promises cross-tenant rejection
   coverage — closing this (root cause: stale fixture data or non-isolated
   schema setup across test runs, to be confirmed) is a precondition for
   trusting any other tenant-isolation assertion this pass adds.
4. **The OTP/SMTP email-delivery question the last two audits opened is
   still open.** `diagnose-otp-email-delivery-failure` traced a live dev
   failure to a diagnosability fix (commit `fcee20e`/`dcac61a`) not yet
   reaching `development`, and `verify-email-fix-and-run-tests` flagged the
   fix itself as sitting uncommitted. Neither could close the loop from
   this environment (no network route to the dev server or its logs). The
   user's "all emails where sending and receiving properly" needs that
   status stated plainly rather than left in two half-finished prior
   changes.

## What Changes

- Establish one current, workflow-ordered test matrix covering every
  feature router (`auth`, `tenant`, `platform`, `org_structure`, `visitors`,
  `invitations`, `approvals`, `registrations`, `identity_verification`,
  `notifications`, `reports`, `sso`) plus the two cross-feature `tests/
  test_workflow_*.py` scenario files — this supersedes the stage matrices in
  the four prior changes' `design.md` files rather than re-deriving them
  from zero, folding forward what they already confirmed (API-01..API-19,
  including SSO) and adding the one stage none of them had: **Notifications
  (push)**.
- For the Notifications stage specifically, verify per
  `docs/features/notifications.md`'s own documented recipient-resolution
  table, not just that an endpoint returns 200:
  - Device register/re-register/reassign/delete (self-service, no
    permission check) — happy path, and that re-registering an
    already-owned token updates in place while a token owned by a
    different user is reassigned.
  - `notify_user`, `notify_role_at_branch`, `notify_step_approver` each
    resolve the *correct* recipient set for a real `UserBranchRole` fixture
    — including the documented `admin`-role exclusion (case-insensitive
    name match) and the zero-holders/no-host "log `WARNING`, no-op, not an
    error" paths. (Re-confirm, don't re-derive: `notifications/tests.py`
    already covers most of this, including its own tenant-isolation test —
    this stage re-runs and spot-extends it rather than starting from zero.)
  - Re-confirm the per-event push recipient/payload assertions already in
    `invitations/tests.py` (`test_*_notifies_host`,
    `test_create_invitation_*_notifies_role`) still hold, then close the
    real gap they share (finding #1): each currently silences the *other*
    channel to a bare no-op. Extend each to also capture the email/SMS
    dispatch call's args (not just patch it away) so one test proves both
    channels fire, to the right recipient, for the same real HTTP request —
    e.g. `POST /invitations/{id}/approve` must show the visitor's email
    dispatch call *and* the host's push dispatch call together.
  - For the Mailpit-verified real-delivery pattern
    `test_send_approval_notification_delivers_email_with_qr_via_mailpit`
    already established (finding #2), add the same real-SMTP-round-trip
    coverage for the events that currently only stub the sender: denial
    notification, reschedule notification, and — highest priority, given
    its live-incident history — OTP request/verify over email
    (`identity_verification/tests.py`).
- Root-cause and fix `test_create_invitation_cross_tenant_visitor_category_
  id_rejected`'s current failure (finding #3 above) using this repo's
  established "smallest correct change, decided once the actual root cause
  is known" posture — a fixture/test-isolation fix if the root cause is
  stale cross-run data, or a service/repository fix if a real tenant-schema
  leak is found. Stop and report instead of guessing if the root cause
  implies a schema/constraint design change.
- State plainly, without re-attempting what the environment cannot do: the
  OTP/SMTP dev-delivery question (finding #4) remains unverifiable from
  this session (no network route to `vmss-dev.mypits.org` or its Azure
  DevOps variable group) — this change's own scope is confirming the
  diagnosability code and its test are present and correct locally, and
  restating the concrete open action items (get `fcee20e`/its successor
  merged to `development` and redeployed; then read the
  `smtp_email_dispatch_failed` log fields) as a closing-summary follow-up
  rather than a task this change can close.
- Fix any other genuine bug the pass surfaces, using the same stop-and-
  report threshold the four prior audits used (fix inline if confined to
  one service/router/repository function and it makes behavior match its
  own already-documented/intended contract; stop and report if it's a
  missing endpoint, an ambiguous "intended" contract, or would need a new
  `Modified Capabilities` entry).
- End with a green `ddev exec uv run pytest`, clean `ruff check`/`ruff
  format --check`, and clean `mypy` on `core`/`auth`/`notifications` (the
  new module touching cross-user dispatch) and any other touched
  strict-scope module, plus a closing summary listing: current suite count,
  every bug fixed, and the two items (OTP/SMTP dev delivery, the four prior
  changes) still open for someone else to act on or archive.
- **Housekeeping note, not new scope**: the four prior "verify everything"
  changes this supersedes should be archived once this change's own
  findings are folded in — flagged here for the closing summary, not
  executed as part of this planning-only proposal.

## Capabilities

### New Capabilities
None.

### Modified Capabilities
None planned. This is a verification and regression-closure pass: every
scenario it adds tests for is already part of each endpoint's or event's
existing, documented/intended contract (`docs/features/notifications.md`'s
recipient-resolution table, `openspec/specs/invitations/spec.md` and
`openspec/specs/approvals/spec.md`'s already-written push-notification
requirements, `testing-standards.md` §2's mandatory permission-denied/
tenant-isolation cases). Fixing the currently-failing test or any other bug
found so behavior matches its own already-documented contract is the same
class of change the four prior audits made without a capability delta. If
the cross-tenant test failure's root cause turns out to require an actual
contract change (not just a fixture/isolation fix), that is out of scope
here and gets flagged as a follow-up in the closing summary instead of
folded in silently. This change sets `skip_specs: true` in `.openspec.yaml`
accordingly.

## Impact

- **Affected test files**: `notifications/tests.py`, `invitations/tests.py`,
  `approvals/tests.py`, plus any other feature's `tests.py` the matrix
  review finds gapped, and potentially `tests/test_workflow_staff_admin.py`
  / `tests/test_workflow_visitor.py` if the dual-channel (email + push)
  assertion is added there instead of per-feature.
- **Possible production-code fixes**: scoped to whatever
  `test_create_invitation_cross_tenant_visitor_category_id_rejected`'s root
  cause turns out to be, plus any other concrete bug the pass finds — not a
  refactor pass.
- **No schema/migration changes planned** beyond confirming the already-
  authored, untracked `alembic_tenant/versions/6f4e364ea9c8_device_tokens.py`
  applies cleanly as part of the pass.
- **No breaking changes.**

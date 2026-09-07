## Why

The user asked for a full pass across every endpoint and scenario: proper
validation everywhere, a coding-standards/duplication/over-engineering review,
verification that the existing test suite is itself valid (not just green),
and confirmation that OTP, QR check-in, email, and push notifications actually
work end to end. This is not remediation of a broken build — a fresh
`ddev exec uv run pytest -q` right now is **707 passed**, and `ruff check`/
`ruff format --check`/`mypy` on `core`/`auth`/`notifications`/
`identity_verification` are all clean. Two prior archived audits
(`2026-09-01-verify-full-api-and-notification-delivery`,
`2026-09-03-add-qr-checkin-security`) already closed the dual-channel
notification gap, added Mailpit-verified real-SMTP tests for OTP/approval/
denial/reschedule, and hardened QR check-in with a signed, time-boxed token.

This pass is due now because a **grounded, evidence-first** audit —
enumerating every router endpoint against `testing-standards.md` §2's
mandatory permission-denied/tenant-isolation coverage, every `schemas.py`
field against `security-architecture.md` §4's real-constraint rule, every
list endpoint against `api-conventions.md` §1's pagination/sort/filter rule,
every mutating/public endpoint against idempotency and rate-limiting rules,
and the notification/OTP/QR code paths against what's actually proven by a
real test versus a stub — surfaces **48 concrete, file:line-cited gaps**
across ten features, none of which the two prior audits (which focused on
notification delivery and QR security specifically) were scoped to find.
Closing this backlog now, while the suite is green, keeps "full test
coverage" from silently regressing behind a passing `pytest` run that
doesn't actually assert what the project's own rules require.

## What Changes

- **Test coverage — tenant-isolation and permission-denied gaps**
  (`testing-standards.md` §2), by feature:
  - `auth`: 10 tenant-isolation gaps, reducing to 7 untested repository
    methods (`UserRepository.get_by_email`, `.get_branch_role_assignment`,
    `.get_by_emails`/`.deactivate_employees_not_in`, `.list_hosts_page`;
    `RoleRepository.get_by_name_case_insensitive`, `.list_page`; the
    resync-permissions bulk path; and `get_current_user`'s own raw query in
    `core/tenancy.py`).
  - `invitations`: 9 tenant-isolation gaps (approve, deny, check-out,
    reschedule, extend, badge issue, badge reprint, watchlist-override,
    track-by-email, and `GET /invitations/{id}`'s `get_with_children`) plus
    1 permission-denied gap (`GET /invitations/{id}` has no test for a
    caller with **no** `invitations:view` at all — the existing 403 test
    only covers a caller scoped to a different branch).
  - `visitors`: 4 tenant-isolation gaps (`list_page` and the create-path
    uniqueness lookups for both visitor-categories and
    approval-workflow-rules — only the single-row `.get()` path is
    currently isolation-tested).
  - `dashboard`: 2 tenant-isolation gaps (`GET /overview`'s
    `upcoming_visitors_preview` call, and `PATCH /upcoming-visitors`
    entirely — it doesn't go through the already-tested
    `DashboardRepository` at all).
  - `approvals`: 1 permission-denied gap (`reject_step` — `approve_step` and
    `delegate_step` both have one, `reject_step` doesn't).
  - `audit_trail`: 2 permission-denied gaps (`GET /reports/{job_id}`,
    `GET /{audit_log_id}` — only 404-with-full-permission is tested today).
  - `org_structure`: no hard gap, but a coverage asymmetry — `GET
    /buildings`, `/floors`, `/reception-desks`, `/security-gates` are only
    isolation-tested at the generic repository `.get()` level, unlike
    `GET /branches`/`GET /departments`, which each have a real HTTP-level
    isolation test through `public_tenant_db`. Bring the four laggards up to
    the same pattern.
  - `platform`, `tenant`, `notifications`, `reports`, `sso`, `registrations`,
    `identity_verification`: audited in full — **no gaps found** (each
    either has complete coverage or a verified, test-proven N/A for a
    category that doesn't apply, e.g. global-schema-only tables).
- **Validation hardening** (`security-architecture.md` §4) — 16 field-level
  findings: unbounded `str`/`int` fields that should carry real Pydantic
  constraints — `LoginRequest.password`/`PlatformLoginRequest.password` (no
  `max_length`), `RoleCreateRequest`/`RoleUpdateRequest.permission_codes`
  (unconstrained list items), `UserCreateRequest.password` (min but no max),
  `org_structure` `badge_expiry_duration_minutes`/`floor_number`/`capacity`
  across create/update/provision schemas (no `ge`/`le` bounds),
  `visitors.FormFieldDefinition.options` (list length bounded, item length
  not), `SsoExchangeRequest.code` (no `max_length`), `AuditReportRequest.
  action`/`.entity_type` (free-text filters, no `max_length`). Bounds will be
  chosen generously enough not to reject any value the current test suite or
  a plausible real request already produces.
- **List-endpoint convention compliance** (`api-conventions.md` §1) — 4
  endpoints deviate: `auth::list_permissions` and `sso::list_role_mappings`
  are unpaginated small catalogs; `platform::list_tenants` is unpaginated
  and will matter once multi-tenant is real (`project-rules.md` explicitly
  warns against assuming a single tenant forever); `invitations::
  list_invitations`'s `status` filter is a raw unconstrained string, unlike
  its sibling `registration_type`/`source` enum filters, despite
  `Invitation.status` being a fixed value set. 3 endpoints additionally lack
  sort support (`list_employee_directory`, `list_tenants`,
  `list_role_mappings`). **Flagged, not silently fixed**: adding a
  pagination envelope or tightening a filter's accepted values is exactly
  the kind of change `api-conventions.md` §2 calls breaking (changes
  response shape / tightens validation on an existing param) — each is
  resolved per-endpoint at apply time as either a genuinely non-breaking
  additive fix, or reported as a follow-up requiring a `/api/v2` prefix,
  never folded into `v1` silently.
- **Idempotency and rate limiting** (`api-conventions.md` §3,
  `security-architecture.md` §2) — re-confirmed, not assumed: every
  documented mutating endpoint (invitation create, both check-in variants,
  check-out, OTP request/verify, walk-in registration) already has
  `Idempotency-Key` support with the correct Redis key convention and TTL,
  and every genuinely public/unauthenticated endpoint already carries a
  `@limiter.limit(...)` decorator. **No changes needed** — kept in scope
  only as a re-confirmed, evidenced negative result, not skipped.
- **Code duplication** (`project-rules.md`) — 3 concrete refactors:
  - `invitations/service.py`: the 8-line "notify host via push" block is
    repeated verbatim across 6 call sites (approve, deny, check-in,
    QR check-in, check-out, reschedule) — extract to one helper.
  - `org_structure/service.py`: the get/update/delete CRUD skeleton
    (404-masks-403 fetch, uniqueness recheck, `exclude_unset` field loop,
    `_commit_or_conflict`, soft-delete) is duplicated ~5× across building,
    floor, department, reception-desk, and security-gate — extract shared
    helpers while preserving each entity's own validation hooks.
  - `org_structure/deps.py`: `authorize_branch_id` and
    `authorize_branch_id_tolerant` are copy-pasted except for one repository
    call — extract a shared `_authorize_branch` taking the already-fetched
    `Branch`.
  - **Explicitly not touched**: `core/emailing.py::SmtpEmailSender` vs.
    `identity_verification/senders.py::SmtpEmailSender` — a documented,
    deliberate duplication per an earlier design's own Non-Goals, not a
    fresh finding.
- **Over-engineering review** (`project-rules.md`) — audited storage
  backend abstraction, permission dependency factories, repository class
  hierarchy, and `core/config.py` settings for unjustified abstraction or
  unvaried config knobs. **No changes needed** — codebase is clean here,
  confirmed rather than assumed.
- **OTP flow verification** (`security-architecture.md` §2) — generation,
  single-use enforcement, expiry, failed-attempt lockout, and
  never-logged-in-plaintext are each backed by a real, already-passing test.
  **No changes needed.**
- **QR check-in flow verification** — the signed/time-boxed Fernet token,
  tamper rejection, expiry rejection (both directions of the check-in/
  check-out cycle), tenant isolation, and idempotency replay are each
  backed by a real, already-passing test. **No changes needed.**
- **Email delivery — close the last 2 stub-only events**: 4 of 6
  notification-triggering email events already have a real Mailpit
  round-trip test (OTP-over-email, approval, denial, reschedule). Add the
  same for the 2 that don't: the invitation-submission tracking email
  (`invitations/tasks.py::send_tracking_notification`) and the daily admin
  rollup email (`reports/tasks.py::_send_tenant_rollup_snapshot`).
- **Push notifications — close one untested code path**:
  `notifications/service.py::notify_role_at_branch`'s zero-holders no-op
  branch (log `WARNING`, skip dispatch) is reachable but every test that
  could exercise it stubs the function itself out rather than calling it for
  real. Add one direct unit test.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

None planned. Every item above closes a gap against a contract this
project's own rule files already state (`testing-standards.md` §2,
`security-architecture.md` §2/§4, `api-conventions.md` §1/§3,
`project-rules.md`'s coding standards) — it doesn't change what any
endpoint's intended behavior is. The one category with genuine
breaking-change risk (list-endpoint pagination/filter fixes) is explicitly
scoped to either a non-breaking fix or a reported follow-up requiring its
own versioned proposal, never an in-place `v1` contract change here. This
change sets `skip_specs: true` accordingly, matching the precedent set by
`2026-09-01-verify-full-api-and-notification-delivery` and
`2026-08-17-core-api-compliance-audit` for the same class of
verification-and-closure pass.

## Impact

- **Affected test files**: `auth/tests.py`, `invitations/tests.py`,
  `visitors/tests.py`, `dashboard/tests.py`, `approvals/tests.py`,
  `audit_trail/tests.py`, `org_structure/tests.py`, `notifications/tests.py`,
  `reports/tests.py` — new test cases only, no existing test's assertions
  change.
- **Affected schema files**: `auth/schemas.py`, `org_structure/schemas.py`,
  `visitors/schemas.py`, `sso/schemas.py`, `platform/schemas.py`,
  `audit_trail/schemas.py` — additive `Field` constraints.
- **Affected service/deps files**: `invitations/service.py`,
  `org_structure/service.py`, `org_structure/deps.py` — internal refactors
  only, no behavior change, covered by the existing (unchanged) test
  assertions for those code paths.
- **Possibly affected router files**: `auth/router.py`, `platform/router.py`,
  `sso/router.py`, `invitations/router.py` — only if a list-endpoint fix
  turns out to be non-breaking; anything breaking is deferred to a follow-up
  proposal instead.
- **No schema/migration changes.**
- **No breaking changes** shipped by this change itself.

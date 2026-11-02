## Why

Almost every planned feature has been built. A full read-only audit of both
repos (2026-10-20) found real defects hidden behind working flows:

- a visitor notification that fails on every run;
- a web roster call that silently deactivates employees;
- admin lists that can read the wrong tenant;
- public endpoints that leak staff PII or allow remote check-in;
- per-request work that will not hold up at real tenant volume;
- rule drift from `.claude/rules/`.

This change fixes those defects and pays down the structural debt without
changing what any existing client sees. Features that are still missing go
into a prioritised gap register instead of being built here.

This is the **API half of a paired change**. The web half lives at
`VMMS_WEB/openspec/changes/audit-and-harden-api-and-web/` and holds the web
spec deltas and tasks. This `design.md` holds the shared decisions and the
gap register for both repos. Ship the API first: the web relies on its
additive fields.

## What Changes

**P0: correctness bugs**
- Fix `send_approval_revert_notification`. It raises `TypeError` on every run
  (it calls `_dispatch` with a `sms_body` argument that doesn't exist), so the
  "approval withdrawn" message never reaches the visitor.
- Fix `send_tenant_rollup_snapshot`. It sets its "sent" marker before sending,
  so a failed send is never retried.
- Make multi-recipient email tasks and the per-invitation notification tasks
  idempotent under redelivery, using per-recipient sent markers.
- Resolve tenant and visit timezones through one helper. It accepts IANA
  names and also the legacy `GMT±HH:MM` values the web stores today, so
  those values no longer fall back to UTC.
- Validate the branch, building and department before uploading files on
  invitation create, so a 422 no longer leaves orphaned objects in storage.

**P1: security hardening (additive by default)**
- Add the missing rate limits on `GET /form-builder/effective`, the local-file
  route and the email-logo route.
- Key rate limits on the real client IP behind a trusted proxy.
- Scope idempotency keys to endpoint, caller and request body, and add an
  in-flight lock, so a key can't replay another endpoint's response (for
  example an OTP `proofToken`).
- Add a request-body size cap and a file-count cap on multipart uploads
  (413).
- Refuse to start outside `local`/`testing` while `JWT_SECRET_KEY` is still the
  placeholder.
- Default the container image's `APP_ENV` to `production`.
- New capability `public-endpoint-hardening`. Unauthenticated access that
  leaks PII or changes state gets a `Deprecation` header now. Strict
  enforcement is opt-in through `PUBLIC_ENDPOINT_HARDENING=true` until the
  Flutter and kiosk clients have moved over. This covers:
  - `GET /auth/employees` and `/hosts/search` (strict mode drops the PII fields)
  - `PATCH /api/v2/invitations/{trackingId}/check-in` (strict mode requires an
    approved device or `invitations:checkin`)
  - `GET /invitations/track?email=` (strict mode requires an OTP proof token)
  - `GET /kiosks` (strict mode requires `kiosks:view`)
- Mask emails in failed-login logs.
- Stop echoing raw Pydantic error text in 422 messages.

**P1: additive contract fixes the web needs**
- `/auth/me` branch roles gain `permissionCodes`, so the web can gate UI by
  permission rather than by role name.
- The invitation list item gains `preferredVisitDate`/`preferredVisitTime`
  and `currentApprovalStep`. This removes the board's one-request-per-card
  detail fetch.
- The detail view surfaces check-in/out devices and primary-contact custom
  fields, where they are missing.

**P2: performance (no contract change)**
- Reuse one S3 client for presigning.
- Drop the implicit `lazy="selectin"` cascade on `User`, `UserBranchRole` and
  `Role`, and load explicitly where needed.
- Add `audit_logs` indexes and `pg_trgm` search indexes.
- Batch the flushes and lookups in the form-builder seed, the employee sync
  and the role resync.
- Stream exports.
- Use a single Celery task-session helper.

**P3: refactor and rule compliance (no contract change)**
- Move the inline `select()` calls in services and tasks into repositories.
- Consolidate the duplicated helpers: `order_clause`, sort maps,
  `current_request_id`, retry kwargs, `PaginationMeta.build`, unique-code
  generation, `url_for_optional` and masking.
- Remove dead code.
- Split `invitations/service.py` (3.2k lines), `router.py` (2.6k) and
  `tests.py` (15.7k) by concern.
- Add audit writes for form-builder, avatar and platform mutations.
- Add strict mypy for `core`/`auth` and the `ANN` lint rules.
- Sync `.env.example`.
- Fix the two spec-drift items (check-out permission wording, and the
  visit-info docstring).

**P4: tests**
- Repair the red suite (QA findings T1–T3) as the safety net for every
  refactor. This lands first and depends on `isolate-test-storage-and-cache`.
- Add the missing tenant-isolation, permission-denied and endpoint tests.

**Gap register**
- Features the product doc asks for that don't exist yet, plus contract
  tightenings that would break clients, are recorded in `design.md` with a
  priority and a proposed follow-up change name. None of them is built here.

No **BREAKING** changes: every external change is additive, or off by
default behind `PUBLIC_ENDPOINT_HARDENING`.

## Capabilities

### New Capabilities
- `public-endpoint-hardening`: deprecation signalling, plus opt-in strict
  enforcement, for the unauthenticated endpoints that expose staff PII or
  change visit state.

### Modified Capabilities
- `rate-limiting`: every unauthenticated endpoint is limited, keyed on the
  trusted client IP.
- `api-compliance-hardening`: idempotency keys are scoped to endpoint, caller
  and body, with an in-flight lock; multipart bodies are size- and
  count-capped.
- `environment-configuration`: placeholder secrets and an unset environment
  are refused outside local/testing.
- `audit-trail`: form-builder mutations, avatar uploads and platform
  (superadmin) actions are audited.
- `auth`: `/auth/me` surfaces effective permission codes per branch role.
- `invitations`:
  - The revert notification is delivered on the contact's channel.
  - The list item surfaces the preferred visit date and time.
  - Check-out permission wording is corrected.
- `org-structure`: the company timezone is resolved consistently, including
  legacy UTC-offset values.

## Impact

- **Code:**
  - `core/` (idempotency, rate_limit, config, storage, timezones, logging,
    celery_app, database helpers, middleware)
  - `invitations/` (tasks, service split, router presenters, repository)
  - `auth/` (models eager-loading, schemas, service)
  - `form_builder/`, `reports/tasks.py`, `platform/`, `org_structure/`,
    `kiosks/`, `visit_info/`
  - `alembic_tenant/` (2 index migrations)
  - `pyproject.toml` (mypy and ruff config)
  - `.env.example`
- **Config:** new settings `PUBLIC_ENDPOINT_HARDENING`,
  `MAX_REQUEST_BODY_BYTES`, `MAX_UPLOAD_FILES` and `FORWARDED_ALLOW_IPS`,
  all with safe defaults.
- **Clients:** the React web gets additive fields only. Flutter and kiosk
  see only `Deprecation` headers until operators turn on strict mode.
- **Ops:** the Dockerfile runs uvicorn with `--proxy-headers`; the
  `pg_trgm` extension is needed in each tenant schema migration.
- **Supersedes:** the web's stale
  `optimize-web-code-reuse-and-performance` (0/44); its still-valid items
  move into the web half.

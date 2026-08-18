## 1. Dependencies & Configuration

- [x] 1.1 `uv add qrcode[pil] python-magic aiosmtplib` (QR generation, real-content MIME
      sniffing per `file-upload-handling.md` §2, SMTP sending per design.md Decision 4).
- [x] 1.2 Add to `core/config.py`/`Settings` + `.env.example`: SMTP host/port/user/password/
      from-address, SMS gateway base settings (placeholder — see design.md Open Questions),
      local storage root path, invitation token TTL default (hours), max ID-proof upload size,
      max group visitors per invitation.
- [x] 1.3 Add invitation-related Redis key namespace constants alongside the existing
      `vmss:{tenant_id}:{feature}:{entity}:{id}` convention (`database-architecture.md` §6) —
      idempotency cache and rate-limit keys for the two public endpoints.

## 2. Storage Interface

- [x] 2.1 Create `core/storage.py`: `save(tenant_id, category, filename, content) -> str`
      (returns storage key) and `url_for(key) -> str`, local-disk-backed implementation under
      the configured root (design.md Decision 3).
- [x] 2.2 Add content validation helper (`python-magic` real MIME check against an
      image/PDF allow-list) used by the storage save path, rejecting outside the allow-list
      per `file-upload-handling.md` §2.

## 3. Data Model & Migration

- [x] 3.1 Create `invitations/models.py`: `Invitation` (tenant-scoped `Base`,
      `TimestampMixin`), `InvitationVisitor`, `InvitationVehicle` per design.md Decision 8 —
      tracking token stored hashed, not plaintext.
- [x] 3.2 Generate and review the `alembic_tenant/versions/` migration for the three new
      tables (additive only, per design.md Migration Plan).
- [x] 3.3 Apply the migration to the local dev tenant schema and confirm
      `alembic_tenant upgrade head` succeeds.

## 4. Schemas

- [x] 4.1 `invitations/schemas.py`: `InvitationCreate`/`InvitationOut` (API-09), extending
      `CamelModel` per `fastapi-architecture.md` §3.
- [x] 4.2 `PrimaryContactIn`, `VisitorIn`, `VisitDetailsIn`, `CarriedItemsIn`, `VehicleIn`,
      `ConsentsIn`, and the composed `SelfRegistrationSubmit` request schema (API-10) matching
      the two example JSON payloads' shape (camelCased on the wire).
- [x] 4.3 `InvitationTrackingOut` (full detail, by tracking ID) and
      `InvitationTrackingSummaryOut` (minimal — tracking ID + status only, by email) per
      spec.md's "Public Lookup by Email Is Rate-Limited and Minimally Revealing" requirement.
- [x] 4.4 Field-level validation: `registrationType` enum, visitor-list empty/non-empty rule
      matching `registrationType` (spec.md "Visitor List Matches Registration Type"), ID proof
      type enum, at-least-one-of email/phone validator reused across primary contact and each
      visitor entry — plus a stricter contact-for-method check on the primary contact
      (`preferredContactMethod: "sms"` requires a phone, `"email"` requires an email), found
      while wiring dispatch and not originally called out in this task.

## 5. Repository Layer

- [x] 5.1 `invitations/repository.py`: `InvitationRepository(TenantScopedRepository)` with
      `get_with_children`, `get_by_tracking_id`, `list_by_primary_contact_email` — eager-loads
      `visitors`/`vehicles` wherever the service or response schema touches them
      (`query-performance.md` §1). No `get_by_tracking_token_hash`/`mark_submitted`: superseded
      by the design correction in group 6 below (a signed-JWT tracking token needs no DB-side
      hash lookup at all; `submit_self_registration` mutates the row in place instead of a
      separate mark-submitted step).
- [x] 5.2 Bulk-insert helper for `InvitationVisitor`/`InvitationVehicle` rows from one
      submission (single statement per table, not a per-row loop —
      `query-performance.md` §2).

## 6. Service Layer

- [x] 6.1 `invitations/service.py::create_invitation` — generates tracking ID + a signed
      invitation JWT, computes expiry from the configured TTL, persists via the repository,
      enqueues the invitation-dispatch task (`background-jobs.md` §5 — `.delay()`, never
      called inline). **Design correction made mid-implementation**: `design.md`'s original
      "hashed token in the DB" plan (Decision 8) turned out to be unworkable — the public
      self-registration endpoint has no bearer token, so nothing else told it which tenant
      schema to resolve. Fixed by making the tracking token itself a signed JWT carrying
      `invitationId`/`tenantId` claims (`core/security.py::create_invitation_token`,
      mirroring the existing access/refresh token machinery), verified with no DB lookup at
      all — see the updated docstring in `invitations/models.py`. `design.md` should be
      updated to match before archiving.
- [x] 6.2 `invitations/service.py::submit_self_registration` — resolves the invitation by id
      (decoded from the signed token by the router/deps layer; expiry is enforced by the JWT's
      own `exp` claim before this function ever runs), checks status (spec.md "Public
      Self-Registration Submission"), validates visitor-list/consent/contact rules, stores
      uploaded ID proof files via `core.storage`, persists visitors/vehicles, transitions
      status to `submitted`, enqueues the confirmation+QR dispatch task.
- [x] 6.3 `invitations/service.py::track_by_tracking_id` and `track_by_email` — the latter
      returns only the minimal summary schema (spec.md's "minimally revealing" requirement).
- [x] 6.4 Wire `Idempotency-Key` handling for `submit_self_registration` per
      `api-conventions.md` §3 (cache response in Redis for ~24h keyed by
      `(idempotencyKey, tenantId)`) — implemented in `router.py` (caches/replays the final
      JSON response), not `service.py`, since it's an HTTP-response-caching concern.

## 7. Async Dispatch

- [x] 7.1 `invitations/notifications.py`: `EmailSender`/`SmsSender` protocol +
      `SmtpEmailSender` implementation (design.md Decision 4). SMS stays an
      `UnconfiguredSmsSender` that raises loudly (no gateway chosen yet — design.md Open
      Questions).
- [x] 7.2 `invitations/tasks.py::send_invitation_link` — idempotent (skips if the invitation
      has moved past `pending` — re-runs are safe per `background-jobs.md` §2),
      `autoretry_for`/`retry_backoff`/`max_retries` declared (`background-jobs.md` §3), binds
      `request_id`/`tenant_schema` into `structlog` context at task start
      (`logging-observability.md` §1), logs `ERROR` with full context on retry exhaustion.
- [x] 7.3 `invitations/tasks.py::send_registration_confirmation` — generates the QR (via
      `anyio.to_thread.run_sync` for the CPU-bound render, design.md Decision 5, reusing the
      same raw tracking token the caller already verified rather than minting a second one)
      and sends the confirmation; same idempotency/retry/logging posture as 7.2.

## 8. Router & Permissions

- [x] 8.1 Add `invitations:create`, `invitations:view`, `invitations:cancel` to
      `auth/rbac_catalog.py::PERMISSION_CODES` (and the test-only mirror list in
      `conftest.py::ADMIN_PERMISSION_CODES`) and grant per design.md Decision 7
      (`admin`/`reception`/`host`: create+view; `security`: view; `visitor`: none).
- [x] 8.2 `invitations/router.py`: `POST /invitations` — `require_branch_permission
      ("invitations:create")` (branch-scoped per design.md Context), `response_model=
      Envelope[InvitationOut]` (`api-documentation.md` §1).
- [x] 8.3 `POST /invitations/{tracking_token}/register` — no auth dependency (tenant instead
      resolved from the signed token via `invitations/deps.py`), `slowapi` rate limit keyed by
      IP (`security-architecture.md` §2), multipart form handling for
      `primaryContactIdProofFile` / `visitorIdProofFiles[]`, `response_model=
      Envelope[SelfRegistrationOut]` (a dedicated response shape, not `InvitationOut` — see
      task 6.1's note: there's no new registration link to hand back on submission).
- [x] 8.4 `GET /invitations/track` — no auth dependency (resolves the single configured
      default tenant — see `invitations/deps.py::track_default_tenant_db`'s docstring for the
      known multi-tenant limitation this leaves open), `slowapi` rate limit, accepts
      `trackingId` or `email` query param (mutually exclusive), returns the appropriate
      schema from task 4.3.
- [x] 8.5 Audit log entries (via `record_audit_log`, following the pattern in
      `visitors/router.py`) for invitation creation (`security-architecture.md` §5). Not added
      for the public self-registration submission: `actor_user_id` would have to be `None`
      (no authenticated actor exists on that path) and the row itself already carries a full
      timestamped record of what was submitted — a `None`-actor audit row added no signal
      `security-architecture.md` §5 cares about (mutating *authenticated* actions), so it was
      left out rather than added just to hit a checklist item.

## 9. Integration

- [x] 9.1 Register `invitations.router.router` in `src/vmss_api/api.py`
      (`fastapi-architecture.md` §7).
- [x] 9.2 Add the `invitations` tag with a description to `_TAGS_METADATA` in `main.py`
      (`api-documentation.md` §2).
- [x] 9.3 Add `docs/features/invitations.md` describing purpose, all four endpoints, and the
      new config knobs (`project-rules.md`'s "New Features" documentation requirement).

## 10. Tests (`invitations/tests.py`)

- [x] 10.1 Factories (`polyfactory`) for `Invitation`, `InvitationVisitor`,
      `InvitationVehicle` (`testing-standards.md` §1).
- [x] 10.2 Happy path: create individual invitation → self-register → track by tracking ID →
      track by email returns minimal summary.
- [x] 10.3 Happy path: create group invitation → self-register with 2+ visitors and 2
      vehicles → verify all rows persisted.
- [x] 10.4 Permission-denied case: `POST /invitations` without `invitations:create`
      (`testing-standards.md` §2).
- [x] 10.5 Tenant-isolation case: an invitation created in one tenant schema is not visible
      via the other tenant's session (`testing-standards.md` §2,
      `auth/tests.py::test_tenant_schema_isolation` as reference).
- [x] 10.6 Validation-rule tests: registration-type/visitor-list mismatch, missing consent,
      visitor with neither email nor phone, disguised-file-type upload rejected, oversized
      upload rejected, expired token rejected, resubmission rejected, cancelled-invitation
      rejected. Also added (found necessary while implementing): a primary-contact
      contact-for-method test (`preferredContactMethod: "email"` with no email on file).
- [x] 10.7 Email-lookup minimal-disclosure test: response contains no ID proof/visitor/
      vehicle detail.
- [x] 10.8 Rate-limit trip test for both public endpoints (`limiter.enabled` is forced off in
      the test environment by `core/rate_limit.py`; both tests flip it on locally).
- [x] 10.9 Idempotency-Key replay test on `POST /invitations/{trackingToken}/register`.
- [x] 10.10 Celery task tests: dispatch task is idempotent against an already-`submitted`
      invitation; retry-exhaustion logs at `ERROR`. Implemented against a fake
      `tenant_session_scope` rather than a real DB row — running the task's own
      `asyncio.run()` requires escaping the test's already-running event loop via
      `asyncio.to_thread`, and a real asyncpg connection opened there and returned to the
      module-level engine's *shared* pool corrupted it for later tests ("attached to a
      different loop" on an unrelated subsequent query) — a real Celery worker process never
      shares a pool with its caller, so the fake avoids an artifact of test threading that a
      real deployment never hits.

## 11. Verification Against Product Requirements

- [x] 11.1 Walk `specs/invitations/spec.md` scenario-by-scenario against the implemented
      endpoints and confirm each has a corresponding passing test from section 10. Every
      requirement's scenarios are covered; see section 10's tests.
- [x] 11.2 Re-run the API-01–08 compliance check noted in `proposal.md` - Impact after this
      change lands, confirming the new `invitations` capability didn't regress any existing
      permission, tenancy, or audit behavior (e.g. `invitations:create` seeded correctly
      alongside the existing catalog, no existing role's permission set unexpectedly changed).
      Confirmed: full suite (155 tests, including every pre-existing API-01–08 test) passes;
      `ADMIN_PERMISSION_CODES` in `conftest.py` and `PERMISSION_CODES` in `rbac_catalog.py`
      both updated together so the admin fixture and the real seed stay in sync.
- [x] 11.3 `ddev exec uv run pytest` full suite green (155 passed); `ruff check`/
      `ruff format --check` clean across the repo; `mypy` clean on `src/vmss_api` (73 files,
      including every touched `core/` module).

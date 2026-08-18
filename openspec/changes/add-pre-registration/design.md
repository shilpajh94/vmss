## Context

See `proposal.md` - Why for motivation. Relevant existing pieces this design builds on:

- `org_structure.deps.get_branch_context`/`require_branch_permission` — the established
  pattern for branch-scoped features (`[[project-auth-access-api]]` memory). An invitation is
  created by an employee at a specific branch (it determines which reception desk/department
  set the "department to visit" field should validate against), so `invitations:create` is a
  branch-scoped permission the same way `org_structure` CRUD is.
- `auth.rbac_catalog.PERMISSION_CODES`/`ROLE_PERMISSIONS` — single source of truth for new
  permission codes and default role grants (`security-architecture.md` §1).
- `core.responses.success_response`/`paginated_response` and `core.schemas.Envelope` — every
  new endpoint follows `api-documentation.md` §1 (`response_model=Envelope[...]`).
- No storage interface, email/SMS provider, or QR/image-validation dependency exists yet in
  this codebase (verified: `pyproject.toml` has no `qrcode`, `Pillow`, `python-magic`,
  `boto3`, or email/SMS SDK; `core/config.py` has no provider settings). This change
  introduces the minimal version of each, scoped to what `invitations` needs today —
  `database-architecture.md` §1 already calls for "one storage interface" and §8 for
  provider config living in `settings`, so this isn't a new pattern, just the first feature
  to need it.
- No `notifications` feature package exists yet. Rather than build the general
  "multi-channel dispatch" system `project-rules.md` describes for `notifications/` ahead of
  need, this change adds only what `invitations` requires (email/SMS send + retry) as
  `invitations/tasks.py`, per `background-jobs.md` §1's "only once a feature has actual async
  work." A future `notifications/` package can absorb this dispatch logic when a second
  feature needs multi-channel notification (e.g. host notification on check-in).

## Goals / Non-Goals

**Goals:**
- API-09–12 as specified in `specs/invitations/spec.md`.
- A storage interface and email/SMS sending path other features can reuse later without
  redesign (interface-first, per `database-architecture.md` §1).
- Every public endpoint rate-limited and every mutating endpoint idempotent, per
  `security-architecture.md` §2 and `api-conventions.md` §3.

**Non-Goals:**
- Evaluating `ApprovalWorkflowRule`s against a submitted invitation. No `visitorCategoryId`
  field exists in the given self-registration payload, so this change has nothing to
  associate a category with yet; approval evaluation stays owned by the not-yet-built
  `approvals` feature (`[[project-visitor-types-api]]` memory, point 5).
- Cancel/reschedule invitation, employee "view history"/"approve requests" dashboards. The
  product PDF's Employee Features list (page 10) names these, but the user's API-09–12 scope
  is create + self-register + dispatch + track only. Flagging this gap explicitly rather than
  silently expanding or silently dropping it (matching this project's existing posture in
  `security-architecture.md` §2 and `file-upload-handling.md` §4): recommend a follow-up
  change once `checkin`/`approvals` exist, since "cancel" and "reschedule" are meaningless
  without a check-in state machine to interact with.
- Recurring invitations (PDF Step 3's open question). One-off single/group only.
- Malware/AV scanning of uploaded ID proof files — already an explicitly flagged
  pre-production open item in `file-upload-handling.md` §4; this change does real content/
  MIME validation but does not add a scanning integration.
- A generic multi-channel `notifications/` package (Teams/Slack/push) — email/SMS only, per
  what API-11 actually asks for.

## Decisions

### 1. Two-phase invitation: employee creates a shell, visitor supplies everything else
`POST /invitations` (API-09) takes only `registrationType` + a minimal primary contact
(name + email/phone + preferred contact method) and returns a tracking ID/token. The visitor
then supplies the full contact record (including ID proof), visitor list, visit details,
items, vehicle, and consent through `POST /invitations/{trackingToken}/register` (API-10).
**Why**: the two given example JSON payloads are self-contained and visitor-authored (a
blank `Full Name` input in the UI screenshot even on a link the visitor already received) —
the employee creating the invite typically knows only who to send the link to, not the
visitor's ID proof or vehicle. Alternative considered: have the employee pre-fill everything
and have the visitor only confirm/upload documents — rejected because it doesn't match the
supplied UI (every field starts empty) or either JSON example (both are complete, freshly
authored payloads with no separate "confirm" shape).

### 2. Token possession is the sole authorization for self-registration
The submission's `primaryContact` overwrites whatever the employee entered at creation; no
identity match (e.g. email equality) is enforced between creation and submission.
**Why**: `security-architecture.md` §2 already establishes the pattern ("QR/invitation tokens
signed and time-boxed... so a leaked/guessed id alone doesn't grant access" — the token itself
*is* the access grant, same as a password-reset link). Requiring the visitor's submitted email
to match the employee's guess at creation would break the common case of an EA/reception
creating the invitation with only a phone number, or a visitor correcting a typo the employee
made.

### 3. Minimal local storage interface now, not the full object-storage tier
`core/storage.py` exposes `async def save(tenant_id: uuid.UUID, category: str, content: bytes,
content_type: str) -> str` (returns a storage key — `content_type` comes from
`validate_upload`'s own magic-byte sniff, not a client-supplied header, so the storage key's
extension is always derived from real content) and `async def url_for(key: str) -> str`, backed
by local disk under a configured root directory in dev. Keys follow
`vmss:{tenant_id}:invitations/id-proof:{uuid}.{ext}` (`database-architecture.md` §6's key
convention, reused for storage keys since none existed to reuse otherwise). Swapping the disk
backend for S3-compatible object storage later is a new implementation of the same two
functions, not a call-site change (`database-architecture.md` §1's explicit requirement).
**Why now**: building the full production S3 integration is out of scope for a single
feature's file upload need and would block this change on an infra decision
(`project-rules.md`'s deployment target is explicitly "not yet decided"); the interface
boundary is what actually matters architecturally, and it's cheap to get right the first time
a feature needs it.

### 4. Email/SMS provider: pluggable sender interface, SMTP + a single SMS gateway adapter
Add `invitations/notifications.py` with an `EmailSender`/`SmsSender` protocol, one concrete
SMTP implementation (`aiosmtplib`, since the project has no email SDK yet and SMTP needs no
new account/vendor to test against in dev — an actual SMS gateway account is a business
decision) and one adapter interface for SMS left to be wired to whatever gateway the client
picks (documented as an open item, not blocking — see Open Questions). Both are called only
from `invitations/tasks.py` Celery tasks, never inline in `router.py`/`service.py`
(`background-jobs.md` §5).

### 5. QR payload is the tracking token itself, not a new secret
The QR code encodes the same signed tracking token used in the registration link (rendered as
a QR via the `qrcode` package, `anyio.to_thread.run_sync`'d since image generation is
CPU-bound per `fastapi-architecture.md` §4). A future check-in endpoint scanning this QR
reuses the same token verification logic already written for API-10 — no second token scheme
to keep in sync.

### 6. Idempotency-Key required on `POST /invitations/{token}/register`
Per `api-conventions.md` §3 — a visitor on a flaky connection retrying a multipart submission
with uploaded files must not create duplicate invitation-visitor rows or send two confirmation
emails. Cached response keyed by `(idempotencyKey, tenantId)` in Redis for ~24h, same as any
other mutating endpoint.

### 7. New permission codes, following the existing `<resource>:<action>` catalog convention
`invitations:create`, `invitations:view`, `invitations:cancel` (reserved now, unused until a
future cancel endpoint exists — added to the catalog so the RBAC seed doesn't need a second
migration when cancel ships). `admin`, `reception`, and `host` get `create`+`view`; `security`
gets `view` only (needs to see pending arrivals, doesn't originate invites); `visitor` stays
empty (the visitor-facing endpoints are unauthenticated by design, not RBAC-gated).

### 8. New tables live in `invitations/models.py`, tenant-scoped (`Base`, not `GlobalBase`)
`Invitation` (one row per API-09 call; holds `registration_type`, `status`, tracking id,
expiry, branch id, primary contact fields, visit detail fields, consent fields, created-by user
id), `InvitationVisitor` (zero-or-more per invitation; group co-visitors), and
`InvitationVehicle` (zero-or-more per invitation). Carried items are stored as a JSONB list +
free-text description directly on `Invitation` (no separate table — same posture as
`VisitorCategory.form_schema`'s JSONB list, since carried items have no independent identity
or per-row actions of their own, unlike visitors/vehicles which get edit/delete rows in the
UI).

**Superseded during implementation**: this decision originally called for storing the tracking
token hashed (like a password/API key) on `Invitation`, with verification recomputing the hash
from the token presented in the URL. That design didn't account for how the token gets
*verified* on a request that carries no bearer token at all — a hash lookup still requires
already knowing which tenant's schema to query it against, which is exactly the piece the
public self-registration endpoint has no other way to determine. Implemented instead as
Decision 9 below: the token is a self-contained signed JWT, and `Invitation` carries no
token/hash column at all.

### 9. The tracking token is a signed JWT carrying `invitationId`/`tenantId`, verified with no DB lookup
`core/security.py::create_invitation_token`/`decode_invitation_token` extend the existing
`_create_token`/`decode_token` JWT machinery (the same one access/refresh tokens use) with a
third token `type`: `"invitation"`, whose payload is `{sub: invitationId, tenant_id: tenantId,
type: "invitation", iat, exp}`. `invitations/deps.py::get_invitation_tenant`/
`get_invitation_tenant_db` decode it to resolve the tenant and open a session bound to that
tenant's schema — mirroring `core/tenancy.py::get_tenant`/`get_tenant_db`'s shape exactly, just
keyed off this token instead of a bearer access token. `GET /invitations/track` still has no
token at all (a visitor who lost their link is exactly who needs it), so it falls back to
resolving `settings.default_tenant_slug` — a known limitation flagged in
`invitations/deps.py::track_default_tenant_db`'s docstring and `docs/features/invitations.md`,
to replace with real hostname/slug-based tenant routing once a second tenant exists.
**Why**: `security-architecture.md` §2 already requires "QR/invitation tokens signed and
time-boxed server-side... never a raw client-supplied id" for exactly this reason — the token
itself has to carry enough to resolve tenancy, since nothing else on an unauthenticated request
can. This also makes the JWT's own `exp` claim the enforcement point for "Invitation Has an
Expiry-Bound Tracking Identity" (spec.md), rather than a separate expiry check in
`service.py`. **Alternative considered**: a hashed opaque token (original Decision 8) — worked
fine for verifying "is this token valid" but never solved "which tenant does this token belong
to" without either a global (all-tenant-schemas) lookup table or a client-supplied tenant id,
the latter being exactly what `security-architecture.md` §3 forbids.

## Risks / Trade-offs

- **[Risk]** SMTP-only email in this change means the client's actual choice of transactional
  email provider (SES, SendGrid, etc.) isn't wired yet. → **Mitigation**: the `EmailSender`
  protocol isolates this to one adapter swap; SMTP against a real mail server still exercises
  the full dispatch/retry/audit path end to end.
- **[Risk]** No SMS gateway is selected yet, so SMS dispatch has no working adapter at merge
  time. → **Mitigation**: `preferredContactMethod: "sms"` still validates and queues the task;
  the task logs at `ERROR` and exhausts retries visibly (`background-jobs.md` §4) rather than
  silently pretending to succeed, so this is a visible gap, not a masked one, until a gateway
  is chosen.
- **[Risk]** Storing the ID-proof file on local disk in dev means it doesn't survive a
  container rebuild. → **Mitigation**: acceptable for dev per `database-architecture.md` §1's
  explicit "local disk in dev" allowance; the interface makes the prod swap a config change.
- **[Trade-off]** Allowing the visitor's submitted contact info to freely overwrite what the
  employee entered at creation (Decision 2) means a mistyped or malicious visitor could submit
  under a different name than the employee intended to invite. → Accepted: the invitation is
  still bound to one specific token/link, so this is equivalent to "whoever has the link
  registers" — the same trust model as any single-use registration link, and reception still
  performs identity verification (ID proof, photo) at actual check-in regardless of what
  pre-registration says.

## Migration Plan

- New Alembic tenant migration (`alembic_tenant/versions/`) adding `invitations`,
  `invitation_visitors`, `invitation_vehicles` — additive only, no existing table touched.
- New `.env`/`settings` keys ship with safe local-dev defaults (SMTP to a dev mailhog-style
  container, local-disk storage root) so existing environments don't break on upgrade; no
  existing key changes meaning or default.
- No breaking change to any existing endpoint or schema — purely additive, so no `/api/v2`
  concern per `api-conventions.md` §2.

## Open Questions

- Which SMS gateway the client wants (Twilio, MSG91, etc.) — doesn't change this change's
  specs, approach, or task breakdown; the adapter interface absorbs whichever is chosen later.
- Exact default token TTL (proposal assumes a configurable default, e.g. 7 days) — a config
  value, not a design decision; tune after the client confirms typical invite-to-visit lead
  time.

## Why

Employees today have no way to invite a visitor ahead of a visit — every visitor must be
walk-in registered at reception. The product spec's Step 3 ("Pre-Registration") and API-09
through API-12 require an employee-initiated invitation flow, a public multi-step
self-registration form the invited visitor fills in before arriving, delivery of that form's
link/QR by email or SMS, and a way for the visitor to check on their own request's status
without an account. None of this exists yet — `invitations/` is not yet a feature package
(the existing packages are `auth`, `core`, `org_structure`, `platform`, `reports`, `tenant`,
`visitors`).

## What Changes

- New `invitations/` feature package (tenant-scoped, per `project-rules.md`'s directory note:
  "pre-registration, QR, recurring invites").
- **API-09** — `POST /invitations` (authenticated: `invitations:create`): an employee creates
  a single or group invitation. Generates a signed, expiry-bound tracking token (the public
  link/QR payload) and an `INV-XXXXXXXX`-style human-readable tracking ID for phone/email
  lookup. A group invitation pre-seeds the expected visitor count; individual visitor
  identities are filled in by the self-registration step, not by the inviting employee.
- **API-10** — `POST /invitations/{trackingToken}/register` (public, unauthenticated,
  rate-limited): the visitor-facing multi-step self-registration submission — primary
  contact, visitor list (individual has zero additional visitors, group has one or more),
  visit details, carried items, vehicles, and consent — as one multipart submission (JSON
  fields alongside `primary_contact.id_proof_file` / `visitors[i].id_proof_file` parts), per
  the six-step wizard UI and the two JSON payload shapes supplied with this change. Rejects
  an expired, already-submitted, or cancelled token.
- **API-11** — invitation-dispatch: on invitation creation, and again once self-registration
  is submitted, dispatch an email/SMS (per each contact's `preferred_contact_method`)
  containing the tracking link; a QR code encoding the tracking token is generated once
  self-registration is submitted and returned to the visitor (embedded in the confirmation
  email/response) for use at check-in. Dispatch is async (Celery), never inline in the
  request path, per `background-jobs.md`.
- **API-12** — `GET /invitations/track` (public, rate-limited): look up an invitation's
  status by tracking ID or by the primary contact's email — never by a raw database id, per
  `security-architecture.md` §3's "no client-supplied id grants access" rule.
- New dependencies: a QR-code library, an image/MIME-sniffing library for upload content
  validation (`file-upload-handling.md` §2), and an email/SMS provider SDK — see `design.md`
  for the specific packages and the new `.env`/`settings` keys they require.
- New minimal storage interface (local disk in dev, per `database-architecture.md` §1) for
  `id_proof_file` uploads — none exists yet in this codebase.

## Capabilities

### New Capabilities
- `invitations`: employee-created single/group visitor invitations, the public multi-step
  self-registration form the invited visitor completes, async email/SMS + QR dispatch on
  invitation and on registration, and the public tracking-lookup endpoint. Covers API-09,
  API-10, API-11, API-12.

### Modified Capabilities
(none — this change only adds the new `invitations` capability; no existing spec's
requirements change)

## Impact

- **New code**: `src/vmss_api/invitations/{__init__.py,router.py,service.py,schemas.py,
  models.py,repository.py,tasks.py,tests.py}`, a new `core/storage.py` interface, new
  `alembic_tenant/` migration for `invitations`, `invitation_visitors`, `invitation_vehicles`
  tables.
- **Modified code**: `src/vmss_api/api.py` (register the router), `src/vmss_api/main.py`
  (OpenAPI tag), `src/vmss_api/auth/rbac_catalog.py` (new `invitations:create`,
  `invitations:view`, `invitations:cancel` permission codes — `host`/`reception`/`admin`
  get `create`+`view`; `visitor` role stays empty since the public endpoints are
  unauthenticated by design), `src/vmss_api/core/config.py` + `.env.example` (email/SMS
  provider + storage settings), `pyproject.toml`/`uv.lock` (new dependencies).
- **Compliance check against the product spec (`Visitor Management System Product
  Configuration.pdf`) for the 8 already-built APIs (API-01–08)**: reviewed against the PDF's
  domain checklist — company/branch/building/floor/department/employee/visitor-category
  setup (Step 1–2), RBAC with Admin/Reception/Security/Host/Visitor roles scoped per branch,
  configurable approval workflow rules, and OpenAPI/versioning/rate-limiting are all present
  and structurally satisfy the corresponding checklist items. No spec-level gap was found
  that this change needs to fix. Two items the PDF poses as open "Questions" remain
  deliberately unresolved, consistent with how this project already flags rather than
  silently under-builds open product questions (`file-upload-handling.md` §4,
  `security-architecture.md` §2): **recurring invites** (PDF Step 3's question) — this
  change's `invitations` capability covers one-off single/group invitations only, not a
  recurring/series invitation; and **fake-entry prevention beyond ID-format validation**
  (PDF Step 5) — deferred to the not-yet-built `checkin` feature, same posture as
  `security-architecture.md` §2 already documents. Neither blocks API-09–12.

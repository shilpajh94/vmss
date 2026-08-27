
# VMSS_API — Visitor Management SaaS Backend

Backend service for the Visitor Management System (VMS) product. Built with Python,
serves the React web portal and Flutter mobile app, backed by PostgreSQL.

Status: **skeleton scaffolded and running** — DDEV-based local environment,
FastAPI + async SQLAlchemy + PostgreSQL 17 + Redis, **schema-per-tenant**
multi-tenancy (a global schema for cross-tenant registry tables, one Postgres
schema per tenant for its own domain tables — see `database-architecture.md`
§2), `tenant`/`platform`/`auth` wired end to end, and RBAC. Coding/architecture
standards live in `.claude/rules/` (project-rules.md, fastapi-architecture.md,
database-architecture.md, security-architecture.md) — read those before adding a
feature; they're enforced by review, not just documented.

## Getting Started

Requires [DDEV](https://ddev.com/) and Docker.

```bash
ddev start                              # builds the web image (installs uv), starts web/db/redis
cp .env.example .env                    # then replace every __PLACEHOLDER__ with a real value —
                                         # each line's comment gives the DDEV-default to paste in
ddev restart                             # picks up .env — also (re)starts the vmss-api,
                                          # vmss-api-celery-worker, and vmss-api-celery-beat
                                          # daemons; without the worker, anything dispatched via
                                          # Celery (e.g. invitation confirmation emails) silently
                                          # queues and never sends; without beat, no scheduled
                                          # task (e.g. the daily reports rollup snapshot) ever
                                          # gets enqueued in the first place
ddev exec uv run alembic upgrade head    # global schema (tenants, superadmins, ...)
ddev exec uv run python scripts/seed_dev_data.py   # provisions the default tenant's own schema +
                                                    # creates admin@example.com / admin12345 in it
```

Pulled new commits? Re-run `ddev exec uv run alembic upgrade head` (global
schema) and `ddev exec uv run python scripts/seed_dev_data.py` (re-applies
any new tenant migrations and RBAC-catalog permission additions to your
existing default tenant — both steps are safe to re-run, idempotent against
an already-current schema/role).

The API is then live at `https://vmss-new-api.ddev.site:8443` (health check at
`/health`, OpenAPI docs at `/docs`). DDEV ships a built-in Mailpit at
`https://vmss-new-api.ddev.site:8026` — every email this API sends in dev
(OTP codes, invitation confirmations) lands there, not a real inbox.

To generate real, visible activity (invitations, OTP requests, a walk-in
registration) against the actually-running server — real emails you can see
in Mailpit, real rows you can browse in the dev database — run
`ddev exec uv run python scripts/seed_demo_workflow.py` (repeatable; each
run adds a fresh, tagged batch rather than becoming a no-op).

To browse the database from Chrome (or any browser): `ddev add-on get
ddev/ddev-adminer` once, then `ddev restart`. Adminer comes up at the URL
`ddev describe` lists for it (e.g. `https://vmss-new-api.ddev.site:9101`) —
log in with System: PostgreSQL, Server: `db`, Username/Password: `db`/`db`
(same as `ddev describe`'s `db` row), then pick the `global` or `tenant_*`
schema to inspect.

```bash
ddev exec uv run pytest          # run tests (spins up a dedicated `vmss_test` DB)
ddev exec uv run ruff check .    # lint
ddev exec uv run ruff format .   # format
ddev exec uv run mypy src        # type-check
```

Adding a dependency: `ddev exec uv add <package>` (commit the updated
`pyproject.toml` + `uv.lock`).

Adding a feature: see `.claude/rules/project-rules.md` §New Features — a new
`src/vmss_api/<feature>/` package with `router.py`/`service.py`/`schemas.py`/
`models.py`/`repository.py`/`tests.py`, registered in `src/vmss_api/api.py`.

> **Naming note**: don't register a DDEV project named `vmss-api` or `vmss-web` —
> those names are already registered globally on at least one dev machine to an
> unrelated, older project (`~/PythonProjects/VMSS/VMMS_API` /
> `VMMS_WEB`, not this one). This project's DDEV name is `vmss-new-api`
> (`.ddev/config.yaml`) precisely to avoid that collision. If you hit a
> "database type does not match" error from `ddev config`/`ddev start`, that's
> almost certainly this — check `ddev list` for a same-named project before
> troubleshooting further.

> **Note on the sections below**: this is the original planning draft from before
> scaffolding. The **authoritative, current** stack/version table, folder layout,
> and dependency list now live in `.claude/rules/project-rules.md` and
> `fastapi-architecture.md` — a few specifics changed during actual setup (e.g.
> the package is `src/vmss_api/`, not `app/`; PyJWT + Argon2 instead of
> python-jose + passlib; `uv` instead of pip/requirements.txt). The sections
> below are kept for the product-requirements context and original reasoning,
> not as the current source of truth on exact paths/package names.

---

## 1. Product Context (from client requirement doc)

Source: `docs/Visitor Management System Product Configuration.pdf`

The client wants a **configurable-not-customized** product usable across industries
(corporate, hospital, school, residential) with this lifecycle:

```
Org Setup → Visitor Types → Invitation/Pre-Registration → Visitor Registration
  → Identity Verification → Approval Workflow → Check-In → Host Notification
  → Access Control → Check-Out → Emergency Management → Reports & Analytics
  → Administration & Integrations
```

Key non-negotiables called out in the doc that directly affect backend architecture:

- **Multi-tenant-capable SaaS** (client is starting single-tenant, must not be hard to
  flip to multi-tenant later)
- Multiple branches / buildings / floors / departments per organization
- Configurable visitor types, forms, approval workflows, notification templates —
  admin-driven, not developer-driven
- Full **audit trail** (who did what, when — needed for compliance + emergency reports)
- Integrations: HRMS, AD/LDAP, Azure AD (SSO), Email, SMS, WhatsApp, Calendar,
  access control/biometric/CCTV/badge printers
- RBAC across Admin / Employee / Reception / Security roles
- One-click "who is inside the building right now" for emergencies

Everything below is designed against these constraints.

---

## 2. Proposed Stack

| Layer | Choice | Why |
|---|---|---|
| Language | Python 3.12+ | |
| API framework | **FastAPI** | Async I/O (needed for fan-out notifications, external integration calls), Pydantic-validated request/response contracts that React & Flutter teams can consume directly via auto-generated OpenAPI/Swagger, native WebSocket support (real-time host notifications), lighter footprint than Django since there's no server-rendered UI to serve |
| ORM / migrations | SQLAlchemy 2.0 (async) + Alembic | Mature, explicit control over multi-tenant query scoping (see §3) |
| Database | PostgreSQL 15+ | Client-specified; also gives us Row-Level Security as a future multi-tenant hardening option |
| Cache / broker | Redis | Celery broker, session/OTP cache, config cache |
| Background jobs | Celery + Celery Beat | Notifications (email/SMS/push), scheduled reports, data-retention purges, reminders for pending approvals |
| Auth | JWT (access + refresh) via `python-jose` / `pyjwt`, `passlib[bcrypt]` for hashing | Simple now, SSO (SAML/OIDC/Azure AD) layered on top later via `authlib` without changing the core auth contract |
| File storage | Pluggable: local disk (dev) → S3-compatible (prod) via `boto3` | Visitor photos, ID scans, uploaded documents |
| Docs generation | `qrcode` + `Pillow`, `reportlab`/`weasyprint` | QR invites/passes, badge printing, PDF reports |
| Local dev env | DDEV (generic/custom service project) | Per team request — see §7 |

> Alternative considered: **Django + DRF**. It gives a free admin panel and
> `django-tenants` for schema-per-tenant multi-tenancy out of the box. We're not
> recommending it because (a) there's no server-rendered UI to justify Django's
> weight — React/Flutter own all UI, and (b) `django-tenants`' schema-per-tenant
> model is heavier than what a single-tenant-first rollout needs. Worth revisiting
> only if the client later hard-requires per-tenant DB isolation (e.g. enterprise
> contracts demanding dedicated schemas).

---

## 3. Multi-Tenancy Strategy: single-tenant now, multi-tenant later without a rewrite

> **Superseded.** The shared-schema approach below was the original plan and
> was actually built first, but has since been replaced with schema-per-tenant
> (one dedicated Postgres schema per tenant, plus a global schema for
> cross-tenant registry tables) — see `database-architecture.md` §2 for the
> current design and why. Kept here for the original reasoning/history, not
> as current guidance.

Approach: **shared database, shared schema, tenant discriminator column.**

- Every tenant-scoped table carries an `organization_id` FK from day one — even
  though today there will only ever be one row in `organizations`.
- A common declarative base mixin (`TenantScopedMixin`) adds `organization_id` +
  enforces it's never queried without a tenant filter.
- Tenant resolution is a single dependency (`get_current_tenant`) injected into every
  request. Today it always resolves to the one default organization; later it
  resolves from JWT claim / subdomain / header — call sites don't change.
- Data access goes through a **repository layer** (not raw SQLAlchemy calls sprinkled
  through routes), so tenant filtering is enforced in one place, not re-implemented
  per endpoint.
- This avoids the two expensive mistakes: (a) hardcoding "there is only one org"
  logic that has to be hunted down later, and (b) over-building schema-per-tenant
  infrastructure before there's a second tenant to justify it.
- Escalation path if stronger isolation is needed later: add PostgreSQL Row-Level
  Security policies keyed on `organization_id` — no application code changes needed
  since access already goes through the repository layer.

---

## 4. Domain Modules (mapped from the requirement doc)

| Module | Covers |
|---|---|
| **Organization Structure** | Organization (tenant), Branch, Building, Floor, Department, ReceptionDesk, SecurityGate |
| **Identity & Access (RBAC)** | User, Role, Permission, Employee↔OrgStructure mapping |
| **Visitor Master Data** | VisitorType (configurable per industry), Visitor profile, Blacklist, Watchlist, frequent-visitor tracking |
| **Pre-Registration / Invitations** | Invitation, multi-visitor-per-invitation, recurring invitations, QR generation, expiry |
| **Visit Registration** | Visit record, IdentityDocument (Aadhaar/Passport/DL), Photo capture, VehicleDetail, dynamic/custom form fields |
| **Identity Verification** | Verification method (OTP/Face/ID-scan/QR/Barcode/Manual) + VerificationLog |
| **Approval Workflow Engine** | Configurable: single-level, multi-level, auto-approve, auto-reject |
| **Check-In / Check-Out** | CheckInEvent, CheckOutEvent, Badge/Pass issuance, gate tracking, auto-checkout rules, overstay detection |
| **Host Notification** | NotificationTemplate (configurable), multi-channel dispatch (Email/SMS/Push/Teams/Slack), host actions (approve/reject/delay/reschedule) |
| **Access Control** | AccessZone (building→floor→room→restricted area), integration hooks for RFID/Biometric/Turnstile/DoorLock |
| **Emergency Management** | Real-time "visitors currently inside" query, one-click evacuation report |
| **Reports & Analytics** | Daily visitors, by company/department, peak hours, no-shows, overstays, frequent visitors, blacklist hits, contractor hours, visitor history |
| **Admin Configuration** | Visitor type config, workflow config, notification templates, working hours, badge template, dynamic form builder, holiday calendar |
| **Audit & Compliance** | Append-only AuditLog, consent capture, configurable data-retention jobs |
| **Integrations** | Pluggable adapters: HRMS, AD/LDAP, Azure AD (SSO), Email/SMS/WhatsApp gateways, Calendar (Outlook/Google), badge printers, CCTV/biometric/access-control systems |

---

## 5. Proposed Folder Skeleton

```
VMSS_API/
├── app/
│   ├── main.py                     # FastAPI app entrypoint
│   ├── core/
│   │   ├── config.py               # pydantic-settings, env-driven
│   │   ├── security.py             # JWT, password hashing
│   │   ├── tenancy.py              # get_current_tenant dependency
│   │   └── middleware.py           # audit logging, request-id, CORS
│   ├── db/
│   │   ├── base.py                 # Declarative base + TenantScopedMixin
│   │   └── session.py              # async engine/session factory
│   ├── models/                     # SQLAlchemy models, grouped by domain
│   │   ├── org.py
│   │   ├── visitor.py
│   │   ├── invitation.py
│   │   ├── approval.py
│   │   ├── access.py
│   │   └── audit.py
│   ├── schemas/                    # Pydantic request/response models
│   ├── api/
│   │   └── v1/
│   │       ├── auth.py
│   │       ├── organizations.py
│   │       ├── visitors.py
│   │       ├── invitations.py
│   │       ├── checkin.py
│   │       ├── approvals.py
│   │       ├── notifications.py
│   │       ├── access_control.py
│   │       ├── emergency.py
│   │       ├── reports.py
│   │       └── admin.py
│   ├── services/                   # business logic per domain
│   ├── repositories/                # tenant-aware data access layer
│   ├── integrations/               # adapters: email, sms, whatsapp, ad, azuread,
│   │                                #   hrms, biometric, badge_printer, calendar
│   ├── tasks/                       # Celery tasks
│   ├── workers/                     # Celery worker/beat entrypoints
│   └── utils/
├── alembic/                         # DB migrations
├── tests/
├── scripts/
├── .ddev/                           # DDEV config (see §7)
├── pyproject.toml
├── .env.example
└── README.md
```

---

## 6. Core Python Dependencies

```
# API
fastapi
uvicorn[standard]
pydantic>=2
pydantic-settings

# Database
sqlalchemy>=2.0
alembic
asyncpg              # async Postgres driver

# Auth
python-jose[cryptography]
passlib[bcrypt]
python-multipart      # file uploads (photos, ID docs)

# Background jobs / cache
celery
redis

# Domain utilities
qrcode
Pillow
reportlab            # or weasyprint — badge/report PDFs
httpx                # calling SMS/email/HRMS/AD APIs

# Storage (prod)
boto3

# Observability
structlog            # structured logs → feeds AuditLog + ops
sentry-sdk           # optional, error tracking

# Dev/test
pytest
pytest-asyncio
factory-boy
ruff
black
mypy
pre-commit
```

---

## 7. DDEV Setup — as actually built

Superseded the original plan below (kept in git history) once we scaffolded and
tested it for real. DDEV's built-in project types are CMS/PHP-oriented, but the
`generic` project type + `webserver_type: generic` fully supports a non-PHP app —
no custom compose file needed:

```bash
ddev config --project-type=generic --webserver-type=generic \
  --project-name=vmss-new-api --docroot="" --database=postgres:17 \
  --webimage-extra-packages=ca-certificates
```

- **Python**: the ddev-webserver base image (Debian 13/trixie) already ships
  Python 3.13 — no extra packages needed for the interpreter itself.
  `.ddev/web-build/Dockerfile.uv` installs **uv**, which then manages the venv
  from `pyproject.toml`/`uv.lock` (and could pin a different Python version per
  project if we ever needed one — see project-rules.md §Dependency Management).
- **Postgres 17**: `database: {type: postgres, version: "17"}` in
  `.ddev/config.yaml` — validated directly against the actual DDEV Postgres
  images (17 exists as a supported image; 18 does not yet, as of this writing).
- **Redis**: the official `ddev/ddev-redis` add-on (`ddev add-on get
  ddev/ddev-redis`), reachable at `redis:6379` inside the containers — not a
  hand-rolled compose service.
- **Running the app**: `web_extra_daemons` in `.ddev/config.yaml` runs
  `uv run uvicorn vmss_api.main:app --reload` inside the web container;
  `web_extra_exposed_ports` exposes it through `ddev-router` at
  `https://vmss-new-api.ddev.site:8443`. A `post-start` hook runs `uv sync` so
  the venv is always current after `ddev start`/`ddev restart`.

No fallback to a plain `docker-compose.yml` was needed — the generic project type
handled this stack without friction.

---

## 8. API Design Principles

- Versioned REST under `/api/v1/`, OpenAPI/Swagger auto-generated and treated as the
  **contract** shared with the React and Flutter teams.
- Consistent pagination, filtering, sorting conventions across list endpoints.
- Standard error envelope (code, message, field errors) for predictable client-side handling.
- Idempotency keys on check-in/check-out endpoints (kiosk/QR flows can double-submit).
- Outbound webhook events (`visitor.checked_in`, `visitor.approved`, `visitor.overstayed`)
  for downstream integrations (Slack/Teams, access control, CCTV triggers).

---

## 9. Non-Functional Requirements → Implementation Notes

| Requirement (from doc) | Implementation approach |
|---|---|
| Security (encryption, RBAC, audit) | TLS everywhere, RBAC via Role/Permission tables, append-only AuditLog + middleware capturing actor/action/entity/timestamp |
| Performance (fast search, quick check-in) | Async endpoints, DB indexes on visitor search fields (name/mobile/company), Redis-cached config lookups |
| Scalability (multi-branch, high volume) | Stateless API containers behind LB, Celery workers scale independently, connection pooling (pgbouncer as a later addition) |
| Availability | Automated backups, Alembic-versioned migrations, `/health` liveness/readiness endpoints |
| Compliance (data retention, consent) | Consent fields on visitor registration, Celery Beat job for retention-policy purges/anonymization |

---

## 10. Suggested Build Phases

1. Foundation: Auth, RBAC, Org/Branch/Building/Floor/Department (tenant-ready schema)
2. Visitor Types + Visitor registration + Identity docs/photo upload
3. Pre-registration/Invitations + QR + Email/SMS notifications
4. Approval workflow engine (single/multi-level/auto)
5. Check-in/Check-out + Badge generation + Access zones
6. Real-time host notifications (WebSocket) + Teams/Slack
7. Emergency "who's inside" report + Reports & Analytics
8. Admin configuration APIs (dynamic forms, workflow config, templates, holiday calendar, blacklist/watchlist)
9. External integrations (Azure AD SSO, HRMS, AD/LDAP, biometric, badge printers, CCTV hooks)
10. Hardening: audit log completeness, rate limiting, data retention automation, multi-tenant cutover readiness review

---

## 11. Open Questions for the Client (surfaced by the requirement doc)

- Can one company have multiple branches/locations from day one, or is that a phase-2 ask?
- Can multiple visitors be registered under a single invitation?
- Are recurring visitor invitations required for MVP?
- Which fields/forms must be admin-configurable at launch vs. hardcoded for MVP?
- What's the required behavior when a visitor forgets to check out (auto-checkout after N hours? flag only?)
- Is a one-click emergency evacuation report an MVP requirement or phase 2?
- Which integrations are MVP-critical (e.g. Azure AD SSO, HRMS) vs. later (biometric, CCTV, badge printers)?
- Any SLA on data retention / right-to-be-forgotten requirements for compliance?

---

*This is a draft for team review — folder structure, dependency versions, and phase
scoping are open to discussion before we start scaffolding actual code.*

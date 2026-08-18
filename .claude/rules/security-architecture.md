---
trigger: always_on
---

# Security Architectural Standards — VMSS_API

Adapted from the reference `security-architecture.md` (Peace Observatory Backend).
That project was an internal read-mostly API; VMSS_API has real authentication,
handles PII (visitor identity documents, photos), and exposes a few endpoints to
unauthenticated visitors (pre-registration forms, QR check-in, OTP). The rules below
are stricter accordingly.

## 1. Authentication and Authorization

### Authentication
- JWT access + refresh tokens via **PyJWT** (not `python-jose` — less actively
  maintained; PyJWT is the current standard choice for FastAPI).
- Passwords hashed with **Argon2** (`argon2-cffi`), not bcrypt/passlib. Argon2 is
  OWASP's current recommendation (memory-hard, GPU-resistant); `passlib`, which
  the reference project used, has been effectively unmaintained for years and has
  had bcrypt-backend compatibility breakage — don't reach for it.
- Access tokens short-lived (~30 min); refresh tokens longer-lived (~7 days),
  stored client-side only, never logged.

### Role-Based Access Control (RBAC)
- Real RBAC from the start — `Role` and `Permission` tables (many-to-many), not the
  reference project's early-stage `x-admin-role` header shortcut. This product has
  Admin / Employee / Reception / Security roles with genuinely different
  permissions from day one, so there's no "early stage" phase where a header
  stand-in is good enough.
- Permission checks via a reusable dependency factory:
  `Depends(require_permission("visitors:checkin"))` — see
  `fastapi-architecture.md` §6. Don't scatter `if user.role == "admin"` checks
  through service code.

### Tenant Trust Boundary
- `tenant_id` is **never** read from a request body, query param, or path param
  and trusted. For authenticated requests it comes from the JWT claim
  (`core/tenancy.py::get_tenant`); for the unauthenticated visitor-facing
  endpoints (§3) it comes from a signed invitation/QR token, never a raw
  client-supplied id. This is the difference between
  single-tenant-with-a-future-option and a tenant-id-in-the-URL vulnerability
  waiting to be discovered when tenant #2 arrives.
- Under schema-per-tenant (`database-architecture.md` §2) this boundary is now
  enforced twice over: even if a `tenant_id` claim were somehow forged or
  stale, the session it resolves to is bound to exactly one Postgres
  schema — there's no shared table across tenants for a forged id to reach
  into. The claim check still matters (it's what decides *which* schema),
  but a bug here can no longer manifest as one tenant's data leaking into
  another's query result the way it could under column-based tenancy.

### Standardized Security Responses
- **401** — missing/invalid/expired credentials.
- **403** — authenticated but insufficient permission.
- Both go through `error_response` (`fastapi-architecture.md` §5) — same envelope
  shape as any other error, no stack traces, no "which permission you're missing"
  detail beyond what's safe to reveal.

## 2. Public-Facing Endpoints (visitor self-service)

Unlike the reference project, this API has endpoints unauthenticated visitors hit
directly: pre-registration form submission, OTP request/verify, QR-based
check-in/checkout, invitation lookup. These need defenses an internal-only admin
API doesn't:

- **Rate limiting**: `slowapi`, backed by the same Redis instance, on every
  unauthenticated endpoint (OTP request especially — this is the classic
  SMS-bombing / brute-force target). Keyed by IP + endpoint.
- **OTP handling**: short expiry (e.g. 5 min), single-use, invalidated after N
  failed attempts, never logged in plaintext (not even at DEBUG level).
- **QR/invitation tokens**: signed and time-boxed server-side (not just an opaque
  DB id) so a leaked/guessed id alone doesn't grant access.
- **Fake-entry prevention** (flagged as an open question in the product doc): at
  minimum, validate identity document format and require photo capture before a
  visit is marked checked-in; treat this as a product decision to confirm, not
  something to silently under-build.

## 3. Secret Management

- All credentials/keys in `.env`, loaded via `pydantic-settings` into `settings`
  (`src/vmss_api/core/config.py`). Same rule as the reference project.
- `.env` is gitignored; `.env.example` is committed and updated whenever a new
  setting is added — a setting with no corresponding example entry is a bug.

## 4. Data Protection

### Input Validation
- Every API input is a Pydantic model (`fastapi-architecture.md` §3) with real
  constraints (`EmailStr`, `constr`, explicit `max_length` on free-text fields) —
  not just `str`. This matters more here than in a read-mostly API: visitor
  registration forms are exactly the kind of user-supplied-data-becomes-a-PDF/
  becomes-a-badge flow where unvalidated input turns into a rendering or
  injection bug downstream.

### PII Handling
- Identity documents (Aadhaar/passport/DL numbers) and photos are the most
  sensitive data this system holds. Store documents/photos in the object storage
  tier (`database-architecture.md` §1), never inline in the database. Encrypt at
  rest (provider-level SSE at minimum). Access to raw document images is itself a
  permission (`documents:view`), not implied by "can view visitor record."
- Consent capture (per the product doc's compliance requirement) is a required
  field on visitor registration, not an afterthought — record what was consented
  to and when.

### CORS Configuration
- Explicit allow-list of origins (the React portal's domain(s)) in
  `src/vmss_api/main.py`, sourced from `settings`. Never `["*"]`, including in
  staging — Flutter mobile doesn't go through CORS at all (native HTTP client), so
  there's no reason to loosen this for "the app."

### Exception Handling
- A global exception handler (`core/middleware.py`) catches everything unhandled,
  logs the full exception server-side via `structlog`, and returns a standardized
  `error_response` with a generic message — no stack traces, no file paths, no
  SQL fragments in the client-facing response.

## 5. Logging and Auditing

- **Audit trail**: every mutating action (check-in/out, approval decision,
  blacklist change, admin config change, login) is written to an append-only
  `AuditLog` table — actor, tenant, action, entity, timestamp, and (where feasible)
  a before/after diff. This is a product requirement (one-click "who's inside"
  during an emergency depends on this data existing and being trustworthy), not
  just a security nice-to-have.
- **Security events**: failed logins, permission denials, and rate-limit trips are
  logged at `WARNING`; successful admin/security actions at `INFO` — via the
  centralized `structlog` logger, never `print()`.
- Audit writes must not block the request path — write via a background task or a
  Celery task, not inline in the request handler.

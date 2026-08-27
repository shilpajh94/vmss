## Context

See `proposal.md` - Why/What Changes for motivation. Relevant existing state:

- `org_structure/router.py` already mounts an authenticated, branch-scoped
  `GET /departments` (RBAC via `require_branch_scope("departments:view")`).
  It cannot be reused for the kiosk flow (wrong auth model, wrong scoping
  rules), and its path is already taken — the new public endpoint needs a
  different path.
- `auth/models.py::User` is the only "employee" concept in the schema — there
  is no separate `Employee`/`Host` table. It already carries `department_id`,
  `is_active`, `employee_code` (optional), `avatar_url`.
- `registrations/deps.py::get_registration_device` already resolves
  `(tenant, branch_id)` from an optional `X-Device-Key` header (global-schema
  `registration_device_keys`, Argon2-hashed), falling back to
  `settings.default_tenant_slug` + `settings.registration_default_branch_code`
  when the header is absent — a fallback already accepted and documented as a
  trade-off for `POST /registrations/walk-in`.
- No "purpose of visit" or "duration" catalog exists anywhere. Today
  `purpose_of_visit`/`expected_duration` on `Invitation` are unconstrained
  free-text `String` columns, shared verbatim by `invitations` and
  `registrations` via the re-exported `VisitDetailsSubmit`.
- `20/minute`/IP is the established rate limit for public GET/lookup
  endpoints (`GET /invitations/track`, `POST /registrations/walk-in`).

## Goals / Non-Goals

**Goals:**
- Serve host/department/purpose/duration lookups from real tenant data,
  behind the same tenant/branch trust boundary the walk-in submission
  endpoint already uses.
- Let `VisitDetailsSubmit` accept catalog ids without breaking either
  existing consumer (`POST /invitations`, `POST /registrations/walk-in`) or
  any client still sending only free text.
- Give `expected_duration` a machine-usable numeric value (`minutes`) as a
  foundation for future overstay-detection work, without building that logic
  now.

**Non-Goals:**
- Admin CRUD for the new `visit_purposes`/`visit_durations` catalogs — seeded
  once via migration; managing them later is a follow-up.
- Changing `GET /invitations/track`'s response shape to expose the new ids —
  it keeps returning the resolved display strings only, unchanged.
- Any change to `org_structure`'s existing authenticated `/departments`,
  `/branches`, etc.
- Deciding whether "Other" as a purpose should surface a distinct free-text
  UI field — that's an app-side decision; the backend already supports it for
  free via the untouched `purposeOfVisit` string field.

## Decisions

**New package `src/vmss_api/visit_info/`, not folded into `registrations` or `org_structure`.**
The three lookups are their own capability (a new spec, per the proposal),
distinct from `registrations`' one write endpoint and from `org_structure`'s
authenticated admin CRUD. Following `project-rules.md`'s "New Features"
convention: `models.py`, `repository.py`, `service.py`, `schemas.py`,
`router.py`, `tests.py`. It imports `get_registration_device`/
`get_registration_tenant_db` directly from `registrations.deps` rather than
duplicating device-credential resolution — this is an accepted, minor
cross-feature coupling (two features sharing one FastAPI dependency), not a
move to `core/`; `core/tenancy.py`'s "sanctioned exception" precedent is
about `auth`/`tenant`, and promoting device-key resolution to `core/` isn't
warranted by two consumers. Revisit only if a third consumer appears.

**`GET /visit-info/departments`, not `GET /departments`.**
The bare path is already claimed by `org_structure`'s authenticated route.
Grouping the new endpoint under the same `/visit-info` prefix as `/visit-info
/options` also makes the wizard's three lookups discoverable as one group in
`/docs`. This is a deliberate deviation from the literal path in the source
requirement doc, called out explicitly rather than silently changed.

**Host search reads `auth.repository.UserRepository`, department listing reads `org_structure.repository.DepartmentRepository` — `visit_info` does not query `User`/`Department` directly.**
Both repositories already exist and own their models; `visit_info/service.py`
calls one new read method on each rather than `visit_info/repository.py`
re-implementing a second query path against tables it doesn't own
(`database-architecture.md` §3's repository-pattern intent extends naturally
to "don't duplicate another feature's queries," even though the letter of
the rule is about who may hold an `AsyncSession`). `visit_info/repository.py`
only owns the two new catalog tables.

**"Host" = active `User`, no `employee_code` requirement.**
Answers the source doc's open question: excludes deactivated employees
(`is_active = False`, consistent with `org-structure`'s "deactivated, never
deleted" directory-sync behavior) but does not require `employee_code` to be
set, since that field is optional directory metadata, not a gate on being a
valid visit host. Search matches `full_name`/`email` via case-insensitive
`ILIKE`, minimum query length 2, `limit` default 10 / max 25 (kiosk dropdown
sizing, mirroring the `page_size` cap convention).

**New tenant-scoped tables `visit_purposes`/`visit_durations`, not enum columns or a config file.**
A tenant schema table (not `GlobalBase`) matches how every other tenant
domain concept lives (`database-architecture.md` §2), lets `Invitation` hold
a real FK, and gives `duration` a numeric `minutes` value strings can't carry.
Each row: `id`, `name`, `minutes` (durations only), `is_active`,
`sort_order`, `TimestampMixin`, soft-deleted (`deleted_at`) rather than hard
deleted — a row referenced by a historical `Invitation.duration_id`/
`purpose_id` FK must not disappear out from under it. Seeded via an
`alembic_tenant/` data migration with the exact six purposes / five durations
already hardcoded in the app (`Full day` = 480 minutes, assuming an 8-hour
business day — flagged as an assumption, easily corrected in the seed data if
wrong).

**`VisitDetailsSubmit` gains four optional id fields; free text stays authoritative for storage, ids are validate-then-overwrite, not validate-then-store-separately-only.**
Chosen over a hard cutover to ids (rejected: breaking, requires a
coordinated release per `api-conventions.md` §2, and this endpoint already
has real client usage) and over "ids are accepted but ignored, still fully
resolved client-side" (rejected: doesn't satisfy the spec's stated
data-integrity goal at all — a client could send a mismatched id/string pair
and the string would win). Server-side overwrite means: once an id
validates, the stored string is always the canonical name, never trusts
client-supplied text for that field — but a caller that sends only the
string still works exactly as today. `Invitation` gains four nullable FK
columns (`purpose_id`, `host_id` → `users.id`, `duration_id`,
`department_id`) alongside the existing string columns, mirroring the
existing nullable `created_by_user_id` FK pattern already on that model.

## Risks / Trade-offs

- **Host search exposes employee email addresses to the same device-key
  trust boundary already accepted for the walk-in write endpoint** (falls
  back to a default tenant/branch when no `X-Device-Key` is presented,
  exactly like `POST /registrations/walk-in` does today). This is an existing,
  documented trade-off, not a new one introduced here — flagged again because
  this is the first *read* endpoint exposing PII (email) under that
  boundary, which is a slightly different risk shape than a write endpoint.
  → Mitigation: capped `limit` (max 25), minimum query length, rate limiting;
  revisit if this trade-off is reconsidered for the write endpoint.
- **Two features (`registrations`, `visit_info`) importing the same
  dependency function** is mild coupling. → Mitigation: documented above as a
  deliberate, revisit-if-a-third-consumer-appears choice, not an oversight.
- **`Full day` duration's minute value is an assumption (480 = 8h), not
  stated in the source requirement doc.** → Mitigation: called out here and
  in the seed migration's comment; trivial to correct later since it's a data
  row, not a schema change.

## Migration Plan

1. `alembic_tenant/`: create `visit_purposes`, `visit_durations`; add
   `purpose_id`/`host_id`/`duration_id`/`department_id` nullable FKs to
   `invitations`.
2. `alembic_tenant/`: seed `visit_purposes`/`visit_durations` with the six/five
   rows currently hardcoded in the app.
3. Ship `visit_info` package + router registration. Since every new field on
   `VisitDetailsSubmit` is optional and every new endpoint is net-new, this
   deploys with zero coordination required with the web/mobile app teams —
   they adopt the new lookups and (optionally, later) the id fields on their
   own schedule.
4. No rollback complexity beyond the standard migration `downgrade()`: the
   new FK columns are nullable and additive, so downgrading drops them
   without affecting any existing string-only data.

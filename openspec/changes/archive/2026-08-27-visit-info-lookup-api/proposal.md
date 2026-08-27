## Why

The walk-in registration wizard's "Visit Info" step (step 2) currently sources
Purpose and Duration from a hardcoded list baked into the app, and lets the
visitor free-type Host and Department with no backend lookup at all. The
resulting visit record's purpose/duration/host/department values are
therefore unreliable free text — not tied to any real employee or department
row, not analyzable, and not trustworthy input for the emergency "who's
inside" report or a future department-aware approval rule. This replaces all
four with real, backend-driven lookups.

## What Changes

- Add a new unauthenticated, kiosk-facing lookup capability, `visit-info-lookup`,
  resolving tenant/branch the same way `POST /registrations/walk-in` already
  does (device-key header, with the same documented default-tenant/branch
  fallback when the header is absent):
  - `GET /hosts/search` — search active employees by partial name/email
    (minimum 2 characters), returning `id`, `name`, `email`, and `department`
    (when the employee has one) so the app can auto-fill Department on pick.
  - `GET /visit-info/departments` — list active departments for the kiosk's
    resolved branch, returning `id`/`name`. **Deliberately not `/departments`**
    — that path already belongs to `org_structure`'s authenticated,
    branch-scoped admin endpoint; reusing it would collide.
  - `GET /visit-info/options` — list configured visit purposes and durations
    together (`{id, name}` each; each duration also carries a canonical
    `minutes` integer), replacing the app's hardcoded fake lists and the
    existing no-op stub behind `ApiEndpoint.visitInfoOptions`.
- Introduce two new tenant-scoped catalog tables, `visit_purposes` and
  `visit_durations`, seeded via migration with the six purposes / five
  durations already hardcoded in the app today, so flipping the app over from
  fake to real data is behavior-neutral on day one. Managing these catalogs
  (admin CRUD) is out of scope for this change — flagged as a follow-up.
- **Not breaking.** `VisitDetailsSubmit` (shared verbatim by `POST /invitations`
  and `POST /registrations/walk-in` — `registrations/schemas.py` re-exports it
  from `invitations/schemas.py`) gains four new *optional* fields —
  `purposeId`, `hostId`, `durationId`, `departmentId` — alongside its existing
  free-text strings (`purposeOfVisit`, `hostNameOrEmail`, `expectedDuration`,
  `departmentToVisit`). When an id is supplied, the server validates it
  against the corresponding catalog/`Department`/`User` row and overwrites
  the paired string field server-side with that row's canonical display value
  (never trusting client-supplied text once an id is given). When every id is
  omitted, behavior is byte-for-byte unchanged. This satisfies the spec's
  data-integrity recommendation without a version bump or a coordinated
  client/backend release, letting the web and mobile app teams switch to
  id-based submission on their own schedule. Selecting "Other" as a purpose
  needs no special handling: the existing free-text `purposeOfVisit` field
  already carries whatever custom text the visitor enters, id or not.
- All three new endpoints are rate-limited (`20/minute` per IP, matching the
  existing public-GET convention used by `GET /invitations/track` and
  `POST /registrations/walk-in`).

## Capabilities

### New Capabilities
- `visit-info-lookup`: host search, branch-scoped department listing, and
  purpose/duration options serving the walk-in registration wizard's Visit
  Info step.

### Modified Capabilities
- `invitations`: `VisitDetailsSubmit` (also used by `registrations`' walk-in
  endpoint) gains optional `purposeId`/`hostId`/`durationId`/`departmentId`
  fields, each validated and resolved server-side when supplied.

## Impact

- New package `src/vmss_api/visit_info/` (`models.py`, `repository.py`,
  `service.py`, `schemas.py`, `router.py`, `deps.py` re-export, `tests.py`)
  plus two new tenant-schema tables (`visit_purposes`, `visit_durations`) and
  a seed-data migration under `alembic_tenant/`.
- `invitations/models.py` (`Invitation`): four new nullable FK columns
  (`purpose_id`, `host_id`, `duration_id`, `department_id`) + accompanying
  `alembic_tenant/` migration.
- `invitations/schemas.py` (`VisitDetailsSubmit`) and `invitations/service.py`:
  new optional fields plus id-resolution/validation logic.
- `registrations`: no code change required — it inherits the schema change by
  reusing `VisitDetailsSubmit` as-is.
- `auth/repository.py` (`UserRepository`) and `org_structure/repository.py`
  (`DepartmentRepository`): each gains one read method (host search, active
  department listing) that `visit_info/service.py` calls into, rather than
  `visit_info` re-implementing queries against tables it doesn't own.
- `api.py`: register the new `visit_info` router. `main.py`: add its
  `_TAGS_METADATA` entry (`api-documentation.md` §2).
- No change to `org_structure`'s existing authenticated `/departments`,
  `/branches`, etc.

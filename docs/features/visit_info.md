# Visit Info Lookup (Walk-in Registration Wizard, Step 2)

Backs the "Visit Info" step of the walk-in registration wizard with real,
backend-driven data in place of the app's previously hardcoded Purpose/
Duration dropdowns and free-text Host/Department inputs. See
`openspec/changes/visit-info-lookup-api/` for the proposal/design this
feature was built from.

`visit_info` owns two new tenant-scoped catalog tables
(`VisitPurpose`/`VisitDuration`) and reads (never writes) `org_structure`'s
`Department` and `auth`'s `User` for the other two lookups — it has no write
endpoints of its own.

## Endpoints

| Method | Path | Auth | Rate limit | Description |
|---|---|---|---|---|
| GET | `/api/v1/hosts/search` | `X-Device-Key` (no bearer token) | 20/minute per IP | Autocomplete search over active employees by partial name/email (`query`, optional, min 2 chars if supplied; optional `limit`, default 10, max 25). Each result includes `id`, `name`, `email`, and `department` (the employee's current department name, if set) so the app can auto-fill Department on pick. |
| GET | `/api/v1/visit-info/departments` | `X-Device-Key` (no bearer token) | 20/minute per IP | Active, non-deleted departments of the branch resolved from the device credential, as `{id, name}`. Deliberately not `/departments` — that path already belongs to `org_structure`'s authenticated, branch-scoped admin endpoint. |
| GET | `/api/v1/visit-info/options` | `X-Device-Key` (no bearer token) | 20/minute per IP | Active visit purposes and durations configured for the tenant, ordered by `sortOrder`. Each purpose is `{id, name}`; each duration additionally carries a `minutes` integer (e.g. "Half day (4 hours)" → `240`). Replaces the app's hardcoded fake lists and the previously no-op `ApiEndpoint.visitInfoOptions` stub. |

Empty results return `200` with an empty array — never `404`.

### `query` is optional on host search

`GET /hosts/search` never requires `query` — this endpoint carries no bearer
token, so (per `security-architecture.md` §2) no client-held parameter on it
should be mandatory either. Omitting `query`, or supplying it blank, returns
a browsable default list of active employees ordered alphabetically by name,
capped by `limit`, in the exact same response shape a matched search
returns. A **supplied** `query` shorter than 2 characters is still rejected
with a validation error — the minimum length only applies once a caller has
actually typed something to search on.

## Tenant/branch resolution

All three endpoints resolve tenant (and, for department listing, branch) the
exact same way `POST /registrations/walk-in` does — see
`docs/features/registrations.md`'s "Device credential authentication"
section, including its documented `X-Device-Key`-absent fallback and
trade-off. This feature adds no second resolution mechanism; it imports
`registrations.deps.get_registration_device`/`get_registration_tenant_db`
directly.

## Seeded catalogs

`visit_purposes`/`visit_durations` are tenant-scoped tables seeded once via
an `alembic_tenant` data migration with the values the app already
hardcoded, so the switch from fake to real data is behavior-neutral on day
one:

| Purpose |
|---|
| Business Meeting |
| Job Interview |
| Delivery / Pickup |
| Personal Visit |
| Vendor / Contractor Work |
| Other |

| Duration | Minutes |
|---|---|
| 30 minutes | 30 |
| 1 hour | 60 |
| 2 hours | 120 |
| Half day (4 hours) | 240 |
| Full day | 480 |

`Full day` = 480 minutes assumes an 8-hour business day — not stated in the
original requirement doc, and easy to correct later since it's a data row,
not a schema change.

Admin CRUD for these catalogs does not exist yet — retiring or adding an
option today means a manual row update/insert (`is_active`/`sort_order`), not
an endpoint call. Rows are soft-deleted, never hard-deleted, since a past
`Invitation.purpose_id`/`duration_id` may still reference one.

## Interaction with invitation/walk-in submission

`POST /invitations` and `POST /registrations/walk-in` (which reuses the
identical `VisitDetailsSubmit` schema) both gained four new *optional*
fields: `purposeId`, `hostId`, `durationId`, `departmentId`. See
`docs/features/invitations.md`'s "Optional catalog ids" section for the
resolve/validate/overwrite behavior when one is supplied.

## Not yet built (flagged, not silently dropped)

- **Admin CRUD for `visit_purposes`/`visit_durations`.** Seeded once at
  migration time; managing them today means a direct DB update.
- **Host search does not require `employeeCode`.** Any active `User` matches
  regardless of whether it has employee-directory metadata — a deliberate
  choice (visit-info-lookup-api/design.md "Decisions"), not an oversight.

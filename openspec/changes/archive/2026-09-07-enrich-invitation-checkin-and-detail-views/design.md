## Context

Three response schemas in `src/vmss_api/invitations/schemas.py` need new
fields: `InvitationDetailOut` (`GET /invitations/{id}`, authenticated,
`invitations:view`-gated) and `InvitationQrCheckInOut` (both
`PATCH /api/v2/invitations/qr/{token}/check-in` and its `/check-out`
sibling — both public/unauthenticated, gated only by possession of the
signed, encrypted QR token). Both are assembled in `router.py` from an
eager-loaded `Invitation` ORM object (`selectinload(Invitation.visitors)` /
`.vehicles`, per `query-performance.md` §1).

**Scoping correction during implementation**: the initial design targeted
`PATCH /api/v2/invitations/{trackingId}/check-in` (`InvitationCheckInOut`).
That endpoint was confirmed to have no `user`/permission dependency at all
(`service.py::check_in_invitation_by_tracking_id`'s docstring: "public,
unauthenticated... no branch authorization check") — a permission-gated
field cannot be added to it, so it is unchanged by this design. The user
confirmed the actual target is the QR check-in endpoint.

Relevant existing constraints:
- `Invitation.primary_contact_id_proof_storage_key` and
  `InvitationVisitor.id_proof_storage_key` are documented as "deliberately
  never resolved to a URL or exposed on any response schema" pending a
  real permission (see the model docstrings in `invitations/models.py`).
  This change is that permission arriving, but only for the one route
  where a permission check is actually possible (`GET /invitations/{id}`).
- `Invitation` has `branch_id` (always set) and an optional `department_id`
  (nullable catalog reference — see `visit-info-lookup-api`). There is no
  `building_id`/`floor_id` column on `Invitation` at all; building is only
  reachable transitively via `Department.floor_id` → `Floor.building_id`,
  both of which are themselves optional.
- `org_structure` already has `Branch`/`Building`/`Department` models, but
  this codebase's established convention for a *cross-package* reference
  like this is a plain FK column with no ORM `relationship()` — see
  `auth/models.py::User.department_id` and the explicit `outerjoin`s in
  `auth/repository.py::list_employees_page` (`Department -> Floor ->
  Building`). This change follows that same pattern rather than adding new
  `relationship()` attributes to `Invitation` that would break that
  convention.

## Goals / Non-Goals

**Goals:**
- Resolve and return branch/building/department + ID-proof detail without
  N+1 queries per `query-performance.md` (one repository fetch per
  invitation, not one query per nested entity).
- Gate the ID-proof document URL by a real permission on the one endpoint
  where a permission check is possible; never add it where no
  authenticated caller exists.
- Keep the change additive at the data layer — no new columns, no
  migration.

**Non-Goals:**
- No change to `PATCH /api/v2/invitations/{trackingId}/check-in`
  (`InvitationCheckInOut`) or the tracking/email lookup endpoints
  (`InvitationTrackingOut`, `InvitationTrackingSummaryOut`) — see
  proposal.md's "Out of scope, unchanged."
- No malware/content scanning of the ID-proof file itself — unaffected by
  this change; still tracked as the open pre-production item in
  `file-upload-handling.md` §4.
- No UI/badge changes.

## Decisions

### 1. New nested schemas, not reuse of `org_structure`'s CRUD `*Out` schemas
```python
class InvitationBranchOut(CamelModel):
    id: uuid.UUID
    name: str
    code: str
    address: str | None
    city: str | None

class InvitationBuildingOut(CamelModel):
    id: uuid.UUID
    name: str
    code: str

class InvitationDepartmentOut(CamelModel):
    id: uuid.UUID
    name: str
    code: str
```
Rationale: a visit record's consumer wants "which building do I walk this
person to," not the full `BuildingOut` shape (`isActive`, `branchId`
restated, etc). Keeping these separate also means a future change to
`org_structure`'s own CRUD schema doesn't silently change what an
invitation response looks like. Shared by both `InvitationDetailOut` and
`InvitationQrCheckInOut`.

### 2. ID-proof fields: `idProofType` everywhere, `idProofUrl` only on the detail view
The primary contact is not an `InvitationVisitorOut` row (per `models.py`,
the primary contact's fields live directly on `Invitation`), so
`InvitationDetailOut` and `InvitationQrCheckInOut` each gain
`primary_contact_id_proof_type: str | None`; only `InvitationDetailOut`
additionally gains `primary_contact_id_proof_url: str | None = None`.

### 3. A dedicated `InvitationVisitorDetailOut`, not `InvitationVisitorOut` reused with an extra field
`InvitationVisitorOut` is reused, unmodified, by **three** response
schemas: `InvitationTrackingOut` (public tracking lookup),
`InvitationCheckInOut` (public tracking-ID check-in), and
`InvitationQrCheckInOut` (public QR check-in/check-out) — none of which
has an authenticated caller. Adding `id_proof_url` directly to
`InvitationVisitorOut` would therefore leak that field (`null`, but
present, and one future edit away from actually being populated "for
consistency") onto all three. Instead, a new `InvitationVisitorDetailOut`
(`id`, `full_name`, `email`, `phone`, `id_proof_type`, `id_proof_url`,
`photo_url`) is used exclusively by `InvitationDetailOut.visitors`;
`InvitationVisitorOut` itself is left completely unchanged (no new field)
and keeps backing the other three schemas. This is a schema-shape decision
specifically to make "no document URL on an unauthenticated response" true
by construction rather than by convention/discipline.

### 4. Permission check shape (detail view only): additive, not a second route
`GET /invitations/{id}` already resolves the caller (`get_current_user`)
and checks `invitations:view` via `authorize_branch_id_tolerant`. Add a
second, non-blocking check — e.g. `user.has_permission("documents:view",
branch_id=invitation.branch_id)` (same `User.has_permission` helper every
other permission check in this codebase already uses — see
`docs/features/auth.md`'s "RBAC is scoped per branch" section), read after
the primary authorization succeeds, used only to decide whether the router
calls `_resolve_document_url` or passes `None`. No such check exists (or
is possible) on the QR endpoints — see Decisions 2-3.

### 5. Branch/building/department resolution: explicit joins, one query per invitation
`invitations/repository.py`'s existing fetch-for-QR-checkin /
fetch-for-detail queries add explicit `outerjoin`s — `Invitation.branch_id
== Branch.id`, and, only reachable when `department_id` is set,
`Invitation.department_id == Department.id`,
`Department.floor_id == Floor.id`, `Floor.building_id == Building.id` —
mirroring `auth/repository.py::list_employees_page`'s established pattern
for this exact cross-package traversal, rather than introducing new
`relationship()` attributes on `Invitation` (see Context). This is a fixed
number of joins added to the existing single query for the invitation, not
a second query, per `query-performance.md` §1.

### 6. Rollout: existing role-resync endpoint delivers the new permission to live tenants
No migration needed for the permission catalog itself
(`auth/rbac_catalog.py`'s `PERMISSION_CODES`/`ROLE_PERMISSIONS` are
Python-level seed data). For tenants provisioned before this change ships,
an admin (`roles:manage`) triggers the existing "resync standard roles"
endpoint (`POST /auth/roles/resync-permissions`) to backfill
`documents:view` onto their Reception/Security roles — the same path
already used for every prior permission addition. No new migration or
backfill script needed.

## Risks / Trade-offs

- [A tenant that customized Reception/Security's permissions away from the
  catalog default doesn't automatically get `documents:view`] → Expected
  and correct: the resync only adds catalog-default permissions, never
  overrides an admin's deliberate customization (existing resync
  semantics, "A custom grant beyond the catalog default survives").
  Document this in the release note so tenant admins know to run resync.
- [Someone later "simplifies" the detail-view serializer by reusing the
  shared `InvitationVisitorOut` and bolting a document URL onto it,
  silently reintroducing `idProofUrl` on the three public schemas that
  also use it] → Mitigated by Decision 3 (a separate
  `InvitationVisitorDetailOut`, so `InvitationVisitorOut` itself never
  gains the field at all) and the explicit spec scenario "ID-proof type is
  present but the document image is not," which a test in task 5 asserts
  directly.
- [Adding branch/building/department joins to the QR check-in and detail
  query paths slightly increases their query cost] → Bounded and one-time
  per request (fixed joins, not per-row fan-out); acceptable given both
  are low-volume, human-triggered actions, not hot list endpoints.

## Open Questions

None — the two ambiguities that would have affected scope (document
exposure permission model, and which endpoint "check-in" actually refers
to) were resolved with the user, including a scoping correction made
during implementation once the target endpoint's actual (unauthenticated)
behavior was confirmed against the code; see proposal.md.

## Why

This replaces the approach from the withdrawn `fix-branch-scoping-and-role-
permission-lookup` proposal, per further react/flutter feedback: rather than
relocating `X-Branch-ID` to the request body for POST only, the header
should simply become optional everywhere (GET, POST, PUT, PATCH, DELETE),
and `Idempotency-Key` should stay exactly as it already is (an optional
header on the two endpoints that have it) — just clearly documented as such.
`POST /api/v1/auth/roles`'s `Unknown permission code(s): string` bug still
needs the same fix as before: it's a discoverability gap, not a validation
bug.

## What Changes

- **BREAKING**: `X-Branch-ID` becomes optional (not required) on every
  branch-scoped endpoint — org-structure Building/Floor/Department/
  ReceptionDesk/SecurityGate CRUD, invitation creation, and employee listing.
  Behavior when omitted:
  - **List endpoints** (GET with no id): return rows across every branch the
    caller is authorized for, instead of requiring one branch to be named.
    A caller with a company-wide grant for the list's permission sees every
    branch's rows; a caller with only branch-specific grants sees the union
    of just those branches' rows. Supplying `X-Branch-ID` still narrows the
    result to that one branch, as today.
  - **Single-entity GET/PUT/PATCH/DELETE** (by id): the entity's own branch
    (resolved by looking it up) is authoritative for authorization — the
    header is no longer needed to determine or confirm the branch, since the
    id already does. If sent, it's accepted but not required to match
    anything.
  - **Creation endpoints**: the branch is resolved from a branch-identifying
    field already present in the request body (`branchId` directly, or
    transitively via `buildingId`/`floorId`) when the body has one; only
    `POST /invitations` has no such field today, so it still needs
    `X-Branch-ID` in practice — omitting it there with no other signal
    available is rejected with 400. No new required field is added to any
    request body by this change.
  - A caller with no grant at all for the relevant permission (at any
    branch, company-wide or not) is still rejected with 403.
- No change to `Idempotency-Key`'s behavior (it is already optional on
  invitation creation and walk-in registration) — this change only improves
  its Swagger/OpenAPI description so client teams stop treating it as
  mandatory. No spec delta for this (no behavior change).
- Add `GET /api/v1/auth/permissions` returning the tenant's permission-code
  catalog, and add OpenAPI examples to `RoleCreateRequest`/
  `RoleUpdateRequest`'s `permissionCodes` field, so Swagger's "Try it out"
  stops defaulting to the literal `["string"]` that's producing the
  `Unknown permission code(s): string` reports. Unknown-code rejection
  (404) is unchanged — the gap being fixed is discoverability.

## Capabilities

### New Capabilities

(none — this change extends existing capabilities only)

### Modified Capabilities

- `auth`: adds a permission-catalog lookup endpoint; documents that
  `X-Branch-ID` is optional and how branch scope is resolved when it's
  omitted (list vs. entity vs. creation requests).
- `org-structure`: Building/Floor/Department/ReceptionDesk/SecurityGate
  list, get, update, and delete endpoints no longer require `X-Branch-ID`;
  creation endpoints resolve branch from the body as before.
- `invitations`: invitation creation still needs a branch signal (header,
  since its payload has none) but the header is no longer declared as a
  hard-required parameter at the framework level — a request that supplies
  neither the header nor an authorized default is rejected with 400 instead
  of FastAPI's generic "missing header" 422.

## Impact

- Code: `src/vmss_api/org_structure/deps.py`, `.../router.py`,
  `.../service.py`, `.../repository.py`; `src/vmss_api/auth/models.py`
  (new "which branches is this user authorized for" helper),
  `.../router.py`, `.../schemas.py`, `.../service.py`, `.../repository.py`,
  `.../rbac_catalog.py`; `src/vmss_api/invitations/router.py`.
- Tests: `org_structure/tests.py`, `auth/tests.py`, `invitations/tests.py` —
  existing tests asserting `X-Branch-ID` is required need updating to cover
  the header-omitted paths (list-across-authorized-branches, entity-by-id
  resolution, invitation-creation 400) alongside the header-present paths,
  which keep working unchanged.
- Docs: `docs/features/org-structure.md`, `docs/features/auth.md`,
  `docs/features/invitations.md` need updating for the new optional-header
  semantics and the new `/auth/permissions` endpoint.
- Client teams: React/Flutter can stop sending `X-Branch-ID` on GET/PUT/
  PATCH/DELETE calls entirely once this ships, and can omit it on the four
  org-structure creation endpoints that already send `branchId`/
  `buildingId`/`floorId` in the body; `POST /invitations` still needs it
  sent today, since nothing else in its payload identifies a branch.

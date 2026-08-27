## Why

The employee directory listing (`GET /auth/employees`) needs richer filtering
so the web portal can narrow results by email or role without paging through
the whole branch, and the frontend team has asked to drop the bearer-token
requirement on that endpoint entirely so it can be called without a logged-in
session. Separately, the `SecurityGate` CRUD carries `authMethod` and
`connectivityStatus` fields that are no longer wanted on the gate model.

## What Changes

- Add optional `email` and `role` query filters to `GET /auth/employees`:
  - `email` — exact match against `User.email`.
  - `role` — matches a role name held by the employee via any of their
    `UserBranchRole` assignments (a user with that role in any branch is
    included).
  - Both compose with the existing `departmentId` filter and pagination/sort
    params (AND semantics).
- **BREAKING**: `GET /auth/employees` no longer requires an `Authorization`
  bearer token or the `employees:view` permission. It becomes public, reusing
  the same tenant/branch resolution already established for org-structure's
  public listing endpoints (`org_structure/deps.py::public_tenant_db` /
  `public_branch_scope`): resolve the tenant from a presented access token
  when one is valid, otherwise fall back to `settings.default_tenant_slug`;
  `X-Branch-ID` remains optional and narrows to one branch, otherwise every
  branch's employees are returned (no notion of a caller's authorized
  branches, since there is no caller).
- **BREAKING**: Remove `authMethod` and `connectivityStatus` from
  `SecurityGate` create/update/response schemas and drop the corresponding
  columns from the `security_gates` table via a new tenant migration.
  `highSecurity` and `gateType` are unaffected and stay as-is.

## Capabilities

### New Capabilities

(none)

### Modified Capabilities

- `org-structure`: the "Employee Directory Sync" requirement's listing
  behavior gains `email`/`role` filters and drops its authentication/
  permission requirement; the "Reception Desk and Security Gate CRUD"
  requirement drops the `authMethod` and `connectivityStatus` fields from
  `SecurityGate`'s shape. (Both requirements live in this capability's spec
  even though employee listing is served by `auth/router.py` — that's the
  existing spec organization, not a new split.)

## Impact

- **Code**: `auth/router.py`, `auth/service.py`, `auth/repository.py`,
  `auth/schemas.py` (employee list filter + auth removal);
  `org_structure/models.py`, `org_structure/schemas.py`,
  `org_structure/service.py`, `org_structure/factories.py` (gate field
  removal).
- **Database**: new `alembic_tenant` migration dropping
  `security_gates.auth_method` and `security_gates.connectivity_status`,
  chained after the current head (`a05c36d976c4`).
- **Tests**: `auth/tests.py` gains filter and no-auth-required coverage,
  drops any permission-denied test that assumed `GET /auth/employees` was
  protected; `org_structure/tests.py` drops/rewrites
  `test_create_security_gate_with_offline_connectivity` and
  `test_update_security_gate_connectivity_status`.
- **API consumers**: React portal and Flutter app — both need to stop
  sending a bearer token on this one call (harmless if they still send one,
  since a valid token is still honored for tenant resolution) and stop
  sending `authMethod`/`connectivityStatus` on gate create/update calls.
- **Security note**: making an employee directory (email, phone, designation)
  publicly listable is a real posture change, not just a technical one. This
  proposal implements exactly what was requested, following the existing
  public-listing precedent already in this codebase rather than inventing a
  new trust mechanism — but the product/security decision to expose employee
  PII without authentication should be confirmed by the requester before this
  ships, not just inferred from "the frontend asked for it."

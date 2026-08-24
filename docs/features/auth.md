# Auth

Login + the RBAC primitives (`User`, `Role`, `Permission`) every other feature
depends on. See `security-architecture.md` §1 for the design rationale
(PyJWT + Argon2, real RBAC from day one, tenant resolved from the token — never
from a client-supplied id).

`User`, `Role`, `UserBranchRole`, `AuditLog`, and the `role_permissions` join
table live in **each tenant's own Postgres schema** (`Base`, not
`GlobalBase`) — see `database-architecture.md` §2. `Permission` (the catalog
of what actions *exist*) is the one exception: it's global, since the catalog
is identical for every tenant.

## Endpoints

| Method | Path | Auth | Rate limit | Description |
|---|---|---|---|---|
| POST | `/api/v1/auth/login` | None (public) | 5/minute per IP | Returns an access + refresh token pair. |
| GET | `/api/v1/auth/me` | Any authenticated user | — | The caller's own profile, including its branch-role grants. |
| POST | `/api/v1/auth/users` | `users:manage` (company-wide) | — | Creates a user with no role grants; follow with the branch-roles endpoint below to give it access. |
| POST | `/api/v1/auth/users/{id}/branch-roles` | `users:manage` (company-wide) | — | Grants a role to a user, scoped to one branch (or company-wide when `branchId` is omitted). |
| DELETE | `/api/v1/auth/users/{id}/branch-roles/{assignmentId}` | `users:manage` (company-wide) | — | Revokes a previously granted branch-role assignment. |
| POST | `/api/v1/auth/employees/sync` | `employees:manage` (company-wide) | — | Reconciles the employee directory against a full, authoritative batch — see below. Company-wide by design: one sync call spans every department/branch at once. |
| GET | `/api/v1/auth/employees` | `employees:view` | — | Paginated employee directory (via `department -> floor -> building`), optionally narrowed by `departmentId`. `X-Branch-ID` is optional: scopes to that branch if sent, else every branch the caller holds `employees:view` at. An employee with no `department_id` never appears here. Each row includes `avatarUrl` and the employee's current `branchRoles`. |
| GET | `/api/v1/auth/permissions` | `roles:view` (company-wide) | — | The tenant's full permission-code catalog (`{code, description}`), so a role-creation/update form can populate its permission-code choices instead of guessing. |
| POST | `/api/v1/auth/roles` | `roles:manage` (company-wide) | — | Creates a tenant-defined custom role with a name, optional description, and a set of permission codes (validated against the global catalog — see `GET /auth/permissions` above for discovering valid ones). |
| GET | `/api/v1/auth/roles` | `roles:view` (company-wide) | — | Paginated list of every role in the tenant — the five standard ones plus any custom roles. |
| GET | `/api/v1/auth/roles/verify` | `roles:view` (company-wide) | — | `?name=` availability check (case-insensitive) for a role-creation/rename form, before submitting. |
| GET | `/api/v1/auth/roles/{id}` | `roles:view` (company-wide) | — | A single role's detail. |
| PUT | `/api/v1/auth/roles/{id}` | `roles:manage` (company-wide) | — | Updates a role's description and/or permission set (full replace, not a merge). Renaming one of the five standard roles is rejected. |
| DELETE | `/api/v1/auth/roles/{id}` | `roles:manage` (company-wide) | — | Soft-deletes a custom role. Rejected for a standard role, or for any role with an active `UserBranchRole` grant. |

## Employee directory sync

`User` carries four optional employee-directory columns (`employee_code`,
`designation`, `phone_number`, `department_id` — the last a cross-package FK
into `org_structure`'s tenant-scoped `departments` table, same pattern as
`UserBranchRole.branch_id`). A plain company-wide Admin/Security account
created via `POST /auth/users` has none of them set; only a user reconciled
through the sync endpoint does.

`sync_employee_directory` (`auth/service.py`) treats the posted batch as the
**full, authoritative** employee list, not a delta — this was a deliberate
scope decision (manual bulk sync, no external HRMS/LDAP connector) over
building a real directory-service integration:

- An email not already known becomes a new `User`, created with an unusable
  random password (`secrets.token_urlsafe`) — sync manages directory data
  only, never credentials. There's no password-reset flow yet to hand that
  new user real credentials; that's an open item (see auth's existing
  "not yet built" list below).
- An email already known has its directory fields updated in place and is
  re-activated if it had been deactivated by an earlier sync.
- Every existing employee (`employee_code` set) *not* present in this batch
  is deactivated (`is_active = False`) — company-wide accounts without an
  `employee_code` are never swept in by this.
- Every `departmentId` referenced by the batch is validated to exist before
  anything is written, so one bad row 404s the whole request instead of
  partially applying it.

## Login under schema-per-tenant: the two-hop lookup

A login request carries only an email/password — nothing that says which
tenant, and therefore which schema, to query. `authenticate_user`
(`auth/service.py`) resolves that in two hops, both documented in
`database-architecture.md` §2:

1. Look up the email in the global `tenant_user_index` (`platform/models.py`)
   to get `tenant_id` + `user_id`.
2. Resolve that tenant's `schema_name` (global `tenants` table), open a
   session bound to it (`core/database.py::tenant_session_scope`), and load
   the actual `User` row there to verify the password.

Whenever a `User` is created (`auth/service.py::create_user` —
`register_user`/`scripts/seed_dev_data.py` are the callers today), the same
transaction also writes the `tenant_user_index` row. If those two ever drift
apart, login breaks for that user — there's no query that can reconcile them
after the fact, since the index *is* how the right schema gets found in the
first place.

## `tenant_id` is this system's "company_id"

The product requirement for this feature asks the system to "carry
company_id from day one for future multi-tenant readiness." That field is
`tenant_id`: it's carried on every access/refresh token
(`core/security.py::_create_token`) and bound into every log line for the
request (`core/tenancy.py::get_current_user`). Under schema-per-tenant
(`database-architecture.md` §2), one Postgres schema *is* one company
account, so `tenant_id` and the requirement's "company_id" are the same
concept under a different name — there is no separate `company_id`
column/claim anywhere in this codebase, and that's expected, not a gap.

Don't confuse this with `org_structure.Company` (see
`docs/features/org_structure.md`'s "Company is not `tenant.models.Tenant`"):
that's this tenant's own business profile (legal name, logo, contact info),
exactly one row per tenant schema, with no per-request resolution or context
binding — unlike `X-Branch-ID`, there's no `get_company_context` dependency,
because there's nothing for one to disambiguate.

## RBAC is scoped per branch, not just per tenant

`UserBranchRole` (not a plain `user_id`/`role_id` join) is the actual grant:
`(user_id, role_id, branch_id)`, where `branch_id=None` means the grant
applies to every branch in the company (used for company-wide roles like
Admin) and a concrete id scopes it to that one branch/location — see
`org_structure/deps.py` for how a request resolves *which* branch it's
operating against. `X-Branch-ID` (not a JWT claim) is one way to name it
explicitly, but it's optional everywhere now
(`make-branch-header-optional-and-fix-roles-lookup`) — see
`docs/features/org_structure.md`'s "Branch context" section for the three
resolution paths (list/by-id/create) that apply when it's omitted.

`User.has_permission(code, branch_id=None)` is the single check
`core.deps.require_permission` (branch_id left at its default `None` —
matches only a company-wide grant),
`org_structure.deps.require_branch_permission`/`authorize_branch_id` (passes
a specific branch id — matches a company-wide grant *or* one at that branch),
and by-id routes' own post-fetch check (`user.has_permission(code,
branch_id=<the fetched entity's branch>)`) all build on.
`User.authorized_branch_ids(code)` is the one addition on top: for a list
request with no `X-Branch-ID`, it returns `"all"` (company-wide grant) or the
explicit set of branch ids the caller holds `code` at, so
`org_structure.deps.require_branch_scope` has something other than a single
header value to filter a list query by (`core/schemas.py::BranchScope`).

The five standard roles per `security-architecture.md` §1 — Admin,
Reception, Security, Host, Visitor — live in `auth/rbac_catalog.py`
(`PERMISSION_CODES`/`ROLE_PERMISSIONS`) and are seeded automatically by
`platform/service.py::create_tenant` right after a tenant's schema is
migrated, via `seed_default_roles` — a freshly provisioned tenant has a
usable RBAC catalog with no manual step. `scripts/seed_dev_data.py` imports
the same catalog (calling `seed_default_roles` again is a no-op if it's
already seeded) and only adds the dev-only parts: a default branch, an admin
user, and that admin's company-wide grant.

Reception/Security/Host's default grants also include `buildings:view`,
`departments:view`, and `employees:view` (Reception additionally already had
`desks:view`; Security additionally `gates:view`) — added because their own
portal screens need to browse those lists (e.g. an invitation form's
building/floor picker, `docs/features/invitations.md`'s "Finding the
payload shape" section) and previously had no grant for them at all, not
even at their own branch, so those screens 403'd outright rather than
resolving to an empty/scoped list the way `branches:view` does.

"Visitor" exists in the catalog only to satisfy the five-role requirement
literally — it grants zero permissions, and `assign_branch_role`
(`auth/service.py`) rejects with 409 any attempt to grant it to a `User`.
Visitors never authenticate through this JWT/RBAC system at all
(`security-architecture.md` §2): they're handled by separate, unauthenticated,
signed-token/QR flows, not by a `User` row playing the Visitor role.

### Standard vs. custom roles

A tenant is no longer limited to the five seeded roles — a caller with
`roles:manage` can define any number of additional, tenant-specific custom
roles (`POST /auth/roles`) with their own name, description, and permission
set. `rbac_catalog.STANDARD_ROLE_NAMES` (the five seeded names) is the single
source of truth `auth/service.py`'s role-management functions check against
to reject a rename or delete of a standard role — there's no separate
`is_system` column on `Role` to keep in sync with that list (see
`openspec/changes/add-role-management-and-org-field-gaps/design.md`
Decision 1). A custom role can be freely renamed, have its permission set
replaced, or be deleted, as long as no `UserBranchRole` still grants it
(deleting one that does is rejected with 409 — revoke the grant first via
`DELETE /auth/users/{id}/branch-roles/{assignmentId}`).

`GET /auth/roles/verify?name=` backs a role-creation/rename form's
"is this name available" check — matched case-insensitively against every
non-deleted role (standard or custom) in the tenant, so it catches "Admin"
colliding with "admin" the same way the create/rename endpoints themselves
would reject it.

Beyond the catalog itself, org-structure resources (Building/Floor/
Department/ReceptionDesk/SecurityGate) and the employee directory enforce
branch-scoping in practice, not just in the data model — see
`docs/features/org_structure.md`'s "Branch context" section for how a
by-id request is checked against a resource's *actual* branch, not just
whatever `X-Branch-ID` (if any) was sent.

### Discovering valid permission codes

`GET /auth/permissions` (`roles:view`) returns every permission code in the
catalog, `{code, description}` per entry — built for a role-creation/update
form's permission-code picker, so a client isn't guessing at valid values
(or submitting Swagger's literal `"string"` placeholder, which is what
`Unknown permission code(s): string` reports were actually a symptom of).
`RoleCreateRequest`/`RoleUpdateRequest.permissionCodes` also carry an
`examples` hint now for the same reason. The validation itself is
unchanged: `POST`/`PUT /auth/roles` still reject with 404 if any submitted
code isn't in the catalog (`auth/service.py::_resolve_permission_codes`).

## What's here vs. what's still missing

- **Here**: password hashing (Argon2), access/refresh token issuance (PyJWT)
  carrying a `tenant_id` claim, the `get_current_user` / `get_tenant` /
  `get_tenant_db` / `require_permission` dependency chain
  (`core/tenancy.py`) used by every other feature, branch-scoped RBAC
  (`UserBranchRole`) actually enforced on org-structure/employee endpoints
  (not just modeled), user creation and branch-role grant endpoints,
  automatic RBAC-catalog seeding at tenant provisioning
  (`auth/rbac_catalog.py`), and a tenant-scoped `AuditLog` written on every
  login and mutating action (`auth/audit.py`) — required from day one per
  `security-architecture.md` §5.
- **Not yet built**: refresh-token endpoint (exchanging a refresh token for a
  new access token), logout/token revocation, password reset, user
  deactivation, staff SSO login (the design shows an SSO-only login screen;
  no SAML/OIDC flow exists yet — protocol choice is an open product/infra
  decision).
- Superadmin login (a completely separate identity — not a member of any
  tenant's schema) lives in `platform/`, not here — see
  `docs/features/platform.md`.

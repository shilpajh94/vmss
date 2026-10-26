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
| POST | `/api/v1/auth/login` | None (public) | 3/minute per IP | Returns an access + refresh token pair — **Admin accounts only**; a caller whose account holds no Admin role grant is rejected with 403 even with a correct password. Every other role signs in via SSO instead — see `docs/features/sso_authentication.md`. Rate limit tightened from 5/minute once SSO (API-19) made this endpoint's remaining (Admin) traffic the higher-value brute-force target. |
| POST | `/api/v1/auth/logout` | Any authenticated user | — | Records a `logout` audit entry. Does not invalidate the token — see "Not yet built" below. |
| GET | `/api/v1/auth/me` | Any authenticated user | — | The caller's own profile, including its branch-role grants. |
| POST | `/api/v1/auth/users` | `users:manage` (company-wide) | — | Creates a user with no role grants; follow with the branch-roles endpoint below to give it access. |
| POST | `/api/v1/auth/users/{id}/branch-roles` | `users:manage` (company-wide) | — | Grants a role to a user, scoped to one branch (or company-wide when `branchId` is omitted). |
| DELETE | `/api/v1/auth/users/{id}/branch-roles/{assignmentId}` | `users:manage` (company-wide) | — | Revokes a previously granted branch-role assignment. |
| POST | `/api/v1/auth/employees` | `employees:manage` (company-wide) | — | Creates a single employee, setting `employeeCode`/`departmentId` (required) and optional `phoneNumber`/`designation` directly, plus an optional `password` (8–128 chars; if omitted the account gets an unusable random password, as with sync) — immediately visible via `GET /auth/employees` below, with no sync call needed. Never affects any other employee. |
| POST | `/api/v1/auth/employees/sync` | `employees:manage` (company-wide) | — | Reconciles the employee directory against a full, authoritative batch — see below. Company-wide by design: one sync call spans every department/branch at once. |
| POST | `/api/v1/auth/employees/{id}/disable` | `employees:manage` (company-wide) | — | Reversible disable: sets `isActive=false` and an internal `disabled_by_admin` flag. The employee can't sign in, existing access tokens stop working, and they drop out of host search and `status=active`. Idempotent. `409` if the caller targets themself or the tenant's last active admin. |
| POST | `/api/v1/auth/employees/{id}/enable` | `employees:manage` (company-wide) | — | Re-enables a disabled employee (clears both flags). Idempotent. |
| DELETE | `/api/v1/auth/employees/{id}` | `employees:manage` (company-wide) | — | Soft delete (`204`): the row is kept for historical invitations, but the employee vanishes from every listing, can't sign in, and their email and `employeeCode` are released for reuse (email is tombstoned to `deleted+<id>@invalid.local`, `tenant_user_index` row removed). Same `409` guards as disable. A second delete is `404`. |
| GET | `/api/v1/auth/employees` | None (public) | — | Paginated employee directory (via `department -> floor -> building`) of every non-deleted user in the tenant, not just ones reconciled through the employee-sync flow — an Admin/Security/Reception account with no `employeeCode` still appears. Optionally narrowed by `departmentId`, `email` (exact match), `role` (role name, matched via any branch-role assignment), and/or `status` (`active`/`inactive`, mapped onto `User.is_active`), and/or `search` (free text, max 255 chars: case-insensitive literal substring match on full name, email, or `employeeCode`; blank is ignored; `%`/`_` are not wildcards; ANDed with every other filter and reflected in `pagination.total`). No bearer token or permission required: tenant resolves from a presented access token when valid, otherwise the deployment's default tenant. `X-Branch-ID` is optional: scopes to that branch if sent, else every branch in the resolved tenant. A branch-scoped view returns that branch's employees (department at the branch, or a role grant at it) **plus every all-branch employee** — one with a company-wide role grant, or with no `department_id` and no branch-specific grant — so an all-branch employee shows under every branch (and in the approval delegate picker, `?role=…` + `X-Branch-ID`), once each even if they hold several roles. An employee tied only to other branches is excluded. Each row includes `avatarUrl` and the employee's current `branchRoles`. |
| GET | `/api/v1/auth/permissions` | `roles:view` (company-wide) | — | Paginated permission-code catalog (`{code, description}` rows, `page`/`pageSize` default 1/20, max 100; `sortBy` whitelisted to `code`, default ascending), so a role-creation/update form can populate its permission-code choices instead of guessing. |
| POST | `/api/v1/auth/roles` | `roles:manage` (company-wide) | — | Creates a tenant-defined custom role with a name, optional description, and a set of permission codes (validated against the global catalog — see `GET /auth/permissions` above for discovering valid ones). |
| GET | `/api/v1/auth/roles` | `roles:view` (company-wide) | — | Paginated list of every role in the tenant — the five standard ones plus any custom roles. |
| GET | `/api/v1/auth/roles/verify` | `roles:view` (company-wide) | — | `?name=` availability check (case-insensitive) for a role-creation/rename form, before submitting. |
| GET | `/api/v1/auth/roles/{id}` | `roles:view` (company-wide) | — | A single role's detail. |
| PUT | `/api/v1/auth/roles/{id}` | `roles:manage` (company-wide) | — | Updates a role's description and/or permission set (full replace, not a merge). Renaming one of the five standard roles is rejected. |
| DELETE | `/api/v1/auth/roles/{id}` | `roles:manage` (company-wide) | — | Soft-deletes a custom role. Rejected for a standard role, or for any role with an active `UserBranchRole` grant. |
| POST | `/api/v1/auth/roles/resync-permissions` | `roles:manage` (company-wide) | — | Backfills any catalog permission a standard role (Admin/Reception/Security/Host) is currently missing — see "Resyncing stale roles against the catalog" below. Returns each resynced role's newly granted codes (empty list if it already had everything). |

## Creating a single employee

`POST /auth/employees` (`auth/service.py::create_employee`) is the
single-employee counterpart to the bulk sync endpoint below: it validates the
email isn't already registered and that `departmentId` exists, then creates
the `User` row with `employeeCode`/`departmentId`/`phoneNumber`/`designation`
set directly (same `create_user` helper sync uses), with an unusable random
password like sync. Unlike sync, it never touches any other employee's
`is_active` status — it's scoped to exactly the one row being created.
`departmentId` is required here (sync's equivalent field is optional) because
`GET /auth/employees` inner-joins `department -> floor -> building`; an
employee created without one would never show up in the listing this
endpoint exists to populate.

Before this endpoint existed, the only way to add an employee that would
appear in `GET /auth/employees` was to call the sync endpoint — which treats
its payload as the *entire* directory and deactivates every existing
employee omitted from the batch. Using it to add one employee is exactly the
kind of accidental-mass-deactivation risk this endpoint avoids.

## Employee directory sync

`User` carries four optional employee-directory columns (`employee_code`,
`designation`, `phone_number`, `department_id` — the last a cross-package FK
into `org_structure`'s tenant-scoped `departments` table, same pattern as
`UserBranchRole.branch_id`). A plain company-wide Admin/Security account
created via `POST /auth/users` has none of them set; a user created via
`POST /auth/employees` or reconciled through the sync endpoint does.

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

`documents:view` (Reception and Security only — not Host) gates access to a
resolved ID-proof document image on the invitation check-in/detail
responses, kept separate from `invitations:view`/`invitations:checkin` per
`security-architecture.md` §4 ("access to raw document images is itself a
permission, not implied by can view visitor record") — see
`docs/features/invitations.md`. A tenant provisioned before this permission
existed needs `POST /auth/roles/resync-permissions` run once to backfill it
onto its existing Reception/Security roles, same as any other catalog
addition (see "Resyncing stale roles against the catalog" below).

`roles:view` (Reception and Host) lets those roles' own portal/app screens
call `GET /auth/roles`/`GET /auth/permissions` to resolve role and permission
data client-side when deciding whether to render the approve/delegate
actions on an invitation — without it, that call 403'd for Reception/Host
and the UI had no permission data to act on, so those buttons never
rendered even for a caller who otherwise held `invitations:approve`.
`approval-workflow-rules:view` (Reception and Host) is granted for the same
reason — the invitation form/approval UI needs to read the configured
workflow, not just act on it. A tenant provisioned before either permission
existed needs `POST /auth/roles/resync-permissions` run once to backfill it
onto its existing Reception/Host roles (see "Resyncing stale roles against
the catalog" below).

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
Department/ReceptionDesk/SecurityGate) enforce branch-scoping in practice,
not just in the data model — see `docs/features/org_structure.md`'s "Branch
context" section for how a by-id request is checked against a resource's
*actual* branch, not just whatever `X-Branch-ID` (if any) was sent. The
employee directory listing (`GET /auth/employees`) is the one exception: it
is a public endpoint (see `org_structure.md`'s "Listing endpoints require no
token" section — the same mechanism, reused from `auth/router.py`), so
`X-Branch-ID` there is a plain filter, not an authorization boundary.

### Resyncing stale roles against the catalog

`seed_default_roles` only ever ran automatically once, at
`platform/service.py::create_tenant`'s provisioning time — so a tenant
provisioned before a permission was added to `PERMISSION_CODES`/
`ROLE_PERMISSIONS` had its standard roles permanently missing that grant,
with no way to fix it short of a manual database edit. This already
happened once for real: an early tenant's seeded roles predated
`invitations:create`, so its own admin couldn't create an invitation until
that was noticed and fixed by hand (see `rbac_catalog.py`'s own docstring
on `seed_default_roles`).

`POST /auth/roles/resync-permissions` (`roles:manage`,
`add-invitation-approval-flow-and-role-resync`) fixes this on demand: it
re-runs `seed_default_roles`'s union-merge against the *current* tenant's
already-existing Admin/Reception/Security/Host roles, granting each one any
catalog permission it's currently missing, and reports which codes were
newly granted to which role (an empty list means that role already had
everything). It never removes a permission — not even one a role holds
outside its catalog-default set (a deliberate custom grant survives, the
same trade-off `seed_default_roles` already accepts at provisioning time).
Run it once after adding a new permission to the catalog if existing
tenants need it backfilled, rather than only new tenants getting it from
provisioning onward.

### Discovering valid permission codes

`GET /auth/permissions` (`roles:view`) returns the permission catalog one
page at a time, `{code, description}` per entry, wrapped in the same
paginated envelope (`data` + `pagination`) every other compliant list
endpoint returns — see `api-conventions.md` §1. Built for a
role-creation/update form's permission-code picker, so a client isn't
guessing at valid values (or submitting Swagger's literal `"string"`
placeholder, which is what `Unknown permission code(s): string` reports were
actually a symptom of). A client that wants the whole catalog in one
response (e.g. to render a full checkbox list, as the permission-edit page
does) should pass `?pageSize=100` — the catalog is well under that cap
today. `RoleCreateRequest`/`RoleUpdateRequest.permissionCodes` also carry an
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
  new access token), token revocation (`POST /auth/logout` exists and is
  audited, but does not invalidate the token — see
  `docs/features/sso_authentication.md`'s Known limitations), password
  reset, user deactivation. Staff OIDC SSO login **is** built — see
  `docs/features/sso_authentication.md` (API-19); SAML remains a
  not-yet-built Phase 2.
- **Login method is split by role, not just offered as an alternative**:
  `POST /auth/login` (password) succeeds only for an Admin account;
  Reception, Security, Host, and any tenant-defined custom role
  authenticate exclusively through SSO (`docs/features/sso_authentication.md`).
  This is enforced, not just documented convention — see
  `openspec/changes/separate-admin-staff-login`.
- Superadmin login (a completely separate identity — not a member of any
  tenant's schema) lives in `platform/`, not here — see
  `docs/features/platform.md`.

## Disabling and deleting employees

Disable/enable/delete (`auth/service.py::disable_employee`, `enable_employee`,
`delete_employee`) are audited as `employee_disabled`, `employee_enabled` and
`employee_deleted` (the delete entry's diff keeps the original email, since the
row itself is tombstoned). The last-active-admin check row-locks the active
admin set so two concurrent requests can't remove the last two admins.

Directory sync interaction: an employee disabled through the endpoint keeps
`disabled_by_admin=true`, so a later sync batch still updates their directory
fields but does **not** set them active. An employee sync itself deactivated
(omitted from a batch) is re-activated when they reappear. A deleted employee
is invisible to sync, so a batch containing their email creates a new employee.

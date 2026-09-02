## Context

See `proposal.md` for the verification finding motivating this change.
`notifications/service.py::notify_step_approver` currently reads:

```python
if approver_user_id is not None:
    await notify_user(...)
    return
assert approver_role_id is not None
# role branch: no dispatch call — restrict-invitation-push-to-hosts-only
# removed the notify_role_at_branch(...) call entirely here.
```

`auth/rbac_catalog.py` seeds exactly five standard roles per tenant —
`admin`, `reception`, `security`, `host`, `visitor` — and its own docstring
states these are "non-deletable, non-renameable," so `admin` is a stable,
reliable name to match against regardless of which tenant. `auth/repository
.py::RoleRepository` already inherits `TenantScopedRepository[Role]`, so
`.get(role_id)` resolves a role by id within the tenant-bound session,
consistent with how every other tenant-scoped lookup in this codebase
works.

## Goals / Non-Goals

**Goals:**
- Restore push dispatch to role-identified-step approvers whose role is
  *not* `admin` (Reception, Security, tenant-defined custom roles).
- Keep the `admin` role specifically excluded, as originally intended by
  `restrict-invitation-push-to-hosts-only`'s actual (if imprecisely
  implemented) requirement.

**Non-Goals:**
- Making the excluded role(s) configurable (e.g. a settings list of
  excluded role names) — only `admin` is excluded, per the stated
  requirement; a configurable exclusion list is unrequested scope.
- Touching host-identified-step or terminal-action (approve/deny/
  reschedule/check-in/check-out) push behavior — unaffected by both this
  change and the one it corrects.

## Decisions

### Decision: Match by role name (`admin`), not a hardcoded role id
`approver_role_id` is a per-tenant UUID (`roles` lives in each tenant's own
schema), so there is no single well-known id to compare against across
tenants. The seeded role's `name` is the only cross-tenant-stable
identifier — `rbac_catalog.py` guarantees it can't be renamed or deleted.
`notify_step_approver` resolves the `Role` row via
`RoleRepository(tenant_db).get(approver_role_id)` and compares
`role.name.lower() == "admin"`.

**Alternative considered**: compare `role.permissions` to the full
`PERMISSION_CODES` set (i.e. "is this role the one with every permission,"
rather than "is this role named admin"). Rejected — a tenant could grant a
non-admin role every permission without renaming it, or the seeded `admin`
role's permission set could drift from `PERMISSION_CODES` over time; name
matching a guaranteed-stable, guaranteed-unique identifier is simpler and
matches what "Admin" means to every other part of this codebase (e.g.
`conftest.py`'s own `user` fixture identifies itself as the Admin fixture
by role name, not by permission-set comparison).

### Decision: An unresolvable role dispatches normally (fails open, not closed)
If `RoleRepository(tenant_db).get(approver_role_id)` returns `None` (the
referenced role was deleted after the step was snapshotted — a pre-existing
edge case unrelated to this fix, since `InvitationApprovalStep.approver_role_id`
carries no FK-cascade-delete protection today), `notify_step_approver`
treats that as "not admin" and still calls `notify_role_at_branch` (which
itself already handles "zero holders" as a `WARNING`-logged no-op). Failing
open here is deliberate: silently dropping a push because a role lookup
came back empty would recreate exactly the kind of over-broad, hard-to-
notice suppression this change is fixing.

## Risks / Trade-offs

- **[Risk]** A tenant that renames or repurposes what "Admin" means to them
  by creating a *second*, differently-named role with equivalent
  permissions would still get push for that second role, since only the
  literal name `admin` is excluded. Accepted — matches the stated
  requirement exactly ("Admin didn't want to receive push"), and the
  seeded `admin` role is the only role this system treats as
  non-renameable/canonical.

## Migration Plan

- Pure behavior change in one function body (adds one read query, restores
  one dispatch call under a new guard); no data model, endpoint contract,
  or migration involved. Deploys and rolls back as a plain code change.

## Context

See proposal.md (Why) for the two leak paths. The current state that shapes
the approach:

- `invitations/repository.py::_relevant_to_me_filter` already implements
  clauses (a)–(e), including harden-approval-gate-and-narrow-delegate-visibility's
  "(c) requires the step to be undelegated". Clause (c) does not look at
  the step's role name, so an undelegated `host` step matches every
  `UserBranchRole` holder of `host`.
- `auth/rbac_catalog.py::DELEGATION_ONLY_ROLE_NAMES = {"host"}` is already
  used in two places:
  - `approvals/service.py::_caller_matches_step`: no holder of a
    delegation-only role may *act* on the step purely by role.
  - `notifications/service.py::notify_step_approver`: no such holder is
    *notified*.
  Visibility is the one place that ignores it.
- `GET /invitations/{id}` authorizes with
  `authorize_branch_id_tolerant(..., "invitations:view", invitation.branch_id)`.
  The branch listing uses `require_branch_scope("invitations:view")`. The
  dashboard uses `resolve_dashboard_branch_scope("invitations:view")`.
  `admin`, `reception`, `security`, and `host` all hold `invitations:view`.
- Permissions live in `global.permissions`. Grants live in each tenant's
  `role_permissions`. `seed_default_roles` only union-merges the
  *standard* roles against `ROLE_PERMISSIONS`. It runs on provisioning,
  on `upgrade_tenant_schema` (`scripts/upgrade_all_tenants.py`), and on
  `POST /auth/roles/resync-permissions`. Prestart runs only the global
  migration plus a tenant-drift *warning*.
- Web portal: the admin board (`/admin/invitations`) uses the branch
  listing and `/admin/dashboard/*`. The staff dashboard
  (`/staff/dashboard`) uses `relevantToMe=true` and `GET /invitations/{id}`
  on the rows it gets back.

## Goals / Non-Goals

**Goals:**
- A single definition of "participant" (clauses a–e) that serves both the
  worklist and the detail check, so the two paths cannot drift apart.
- Hosts lose branch-wide read access. Admin, Reception, Security, and any
  existing custom role keep it without anyone re-granting permissions by
  hand.

**Non-Goals:**
- Changing who may approve, reject, or delegate (`approvals` capability).
- Web portal changes. None are needed; see Context.
- Narrowing other invitation-reading endpoints: `lookup-by-email` prefill
  (gated on `invitations:create`), the public `/track`, QR/badge, and
  check-in responses (gated on `invitations:checkin`). Hosts do hold
  `invitations:create`, so the prefill lookup is a separate exposure. It is
  noted under Open Questions, not fixed here.
- The unarchived `delegator-retains-invitation-visibility` idea (a clause
  for "whoever delegated"). Reception is already covered by (e). A
  non-Reception delegator is covered by (d), because they had to act on
  their own step first to gain delegation authority.

## Decisions

### Decision 1: Exclude delegation-only roles inside clause (c), in SQL

Add a join from `current_step.approver_role_id` to `Role`, and a predicate
`func.lower(Role.name).not_in(DELEGATION_ONLY_ROLE_NAMES)`. This goes in
the `current_role_holder` `exists()` subquery. The `lower()` mirrors the
Python checks (`role.name.lower() in ...`). The subquery stays correlated,
with no per-row work (query-performance.md §2).

*Alternative:* resolve the host role's id in the router (like
`default_host_role_id`) and filter `approver_role_id != host_role_id`.
Rejected. It adds a second pre-resolved id to thread through the
router → service → repository, and it would silently diverge if
`DELEGATION_ONLY_ROLE_NAMES` ever gains a member. Matching on name keeps
the one constant as the source of truth.

### Decision 2: A new `invitations:view-all` permission rather than role-name checks

"Branch-wide viewer" becomes a grantable permission. The branch listing,
the detail check, and the dashboard gate consult it through the existing
`require_branch_scope`, `resolve_dashboard_branch_scope`, and
`user.has_permission` helpers, so only the permission strings change.

*Alternatives:*
- (i) Hard-code "is reception/security/admin". Rejected: it violates
  security-architecture.md §1 ("don't scatter role checks") and breaks
  custom roles.
- (ii) Remove `invitations:view` from `host`. Rejected: `seed_default_roles`
  is additive-only, so existing tenants would keep the grant. A tenant
  migration would have to revoke it instead, and a `host` with no grant at
  all would lose the 404-vs-403 distinction in Decision 3.

`invitations:view` stays and means "may view invitations you participate
in at this branch". `invitations:view-all` means "may view every invitation
at this branch".

### Decision 3: Detail check = view-all OR participant; 404 for a non-participant who holds `invitations:view`, 403 for one who holds nothing

In `get_invitation_detail`:

1. Load the invitation (404 if missing, as today).
2. If `user.has_permission("invitations:view-all", invitation.branch_id)`,
   allow. This still goes through `authorize_branch_id_tolerant` so the
   soft-deleted-branch tolerance is kept.
3. Otherwise, resolve `default_host_role_id` and call
   `service.is_invitation_relevant_to(tenant_db, invitation.id, user.id, default_host_role_id)`.
   It uses a new `InvitationRepository.is_relevant_to` that runs
   `select(exists().where(Invitation.id == id_, _relevant_to_me_filter(...)))`,
   which reuses the exact worklist predicate.
4. If the caller is not relevant: return 404 when they hold
   `invitations:view` at that branch, otherwise 403.

A host who holds `invitations:view` can no longer tell "exists, not mine"
from "doesn't exist". A caller with no grant keeps today's 403, so the
status code for that pre-existing condition does not change
(api-conventions.md §2).

*Alternative:* always 403. Rejected at the user's direction ("uninvolved
hosts get 404"). It also leaks less.

### Decision 4: Backfill by tenant data migration, not only `seed_default_roles`

Two changes:

- `ROLE_PERMISSIONS` gains `invitations:view-all` for `reception` and
  `security`. `admin` gets it automatically from `PERMISSION_CODES`. This
  covers new tenants and resync.
- A new `alembic_tenant` revision (`down_revision = "c3d5e7f9a1b2"`,
  the current single head):
  - Inserts `invitations:view-all` into `global.permissions` with
    `ON CONFLICT (code) DO NOTHING`.
  - Inserts a `role_permissions` row for every tenant role that holds
    `invitations:view` and whose `lower(name) != 'host'`, skipping existing
    grants.

  This covers custom roles, which `seed_default_roles` never touches. The
  global table is schema-qualified explicitly. The tenant tables are
  written with `sa.Table(...)` objects (not `sa.table()` or unqualified raw
  SQL), so `schema_translate_map` applies. See the
  `gotcha_sqlalchemy_schema_translate_map` memory. Downgrade deletes the
  `invitations:view-all` grants from this tenant's `role_permissions` and
  leaves the global catalog row alone, because other tenants may still
  reference it.

Because it's a tenant migration, the prestart drift check flags any tenant
that hasn't been upgraded. That makes "Reception suddenly gets 403 on the
branch list" visible instead of silent.

## Risks / Trade-offs

- **[Risk]** Deploy without running `scripts/upgrade_all_tenants.py` means
  Reception and Security get 403 on `GET /invitations` (branch mode),
  `GET /invitations/{id}` for non-participant invitations, and
  `/admin/dashboard/*`. Admin also gets 403 until the grant exists: the
  catalog row is missing until the migration or seed runs. → Mitigation:
  put the upgrade step in the migration plan and `docs/features/invitations.md`.
  The prestart drift warning names the lagging tenant.
- **[Risk]** An unassigned `host` step with no resolved host: Reception
  approved step 0 directly without delegating anyone. That step is now
  visible only to Reception and the Reception user who acted, not to any
  host. This is the intended behavior (Reception must assign it), and it
  matches the existing rule that no host can act on it or be notified.
  → Mitigation: none needed. The web's "Approve & Delegate" already
  assigns step 1 in the same user action.
- **[Trade-off]** The detail endpoint gains up to two extra queries for
  non-view-all callers: the default-host-role lookup and an `exists()`.
  Both are indexed single-row lookups. View-all callers take the fast path
  and skip them.
- **[Risk]** The `invitations` delta modifies the same requirement as the
  unarchived `harden-approval-gate-and-narrow-delegate-visibility` delta.
  → Mitigation: archive `harden-...` first. This delta's MODIFIED text is a
  superset of harden's.

## Migration Plan

1. Merge, then deploy as usual. Prestart runs the global migrations, which
   are unchanged.
2. Run `ddev exec uv run python scripts/upgrade_all_tenants.py`. In
   non-dev environments use the equivalent. This applies the new tenant
   revision and then `seed_default_roles`.
3. Verify: the permission catalog endpoint lists `invitations:view-all`. A
   Reception user still sees the branch list. A second `host` user gets 404
   on a request delegated to someone else.
4. Rollback: `alembic -c alembic_tenant.ini downgrade -1` per tenant
   removes the grants. Revert the code so the gates go back to
   `invitations:view`.

## Open Questions

- Hosts hold `invitations:create`, so `GET /invitations/lookup-by-email`
  can return a prior visitor's prefill data for any email. That is a
  separate, pre-existing exposure outside this bug's scope. Worth a
  follow-up change if hosts shouldn't see other people's visitors' data.

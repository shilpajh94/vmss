## Context

See `proposal.md` - Why. Two independent fixes bundled together because
they were reported in the same batch and both touch the invitations/auth
permission surface.

**Invitation approval today**: `invitations/service.py::create_invitation`
hardcodes `status="submitted"` and unconditionally enqueues
`tasks.py::send_visit_confirmation`, which always attaches a QR PNG. There
is no approve/reject action anywhere in `invitations/router.py` — only
create, list, and the public tracking lookups exist. `Company.
auto_approve_pre_registered_visitors` (`org_structure/models.py`) is
already stored and returned by the Company CRUD endpoints but read by
nothing.

**Role permissions today**: `auth/rbac_catalog.py::seed_default_roles` is
only ever called once, from `platform/service.py::create_tenant` at
provisioning time. Its own docstring already documents the failure mode
this proposal's second half fixes: a tenant provisioned before a
permission was added to `PERMISSION_CODES`/`ROLE_PERMISSIONS` has roles
permanently missing that permission, with no way to backfill short of a
manual database edit — which is almost certainly the cause of the
"Insufficient permission" on invitation listing reported alongside this
change, since the catalog itself already lists `invitations:view` for
every non-Admin staff role.

## Goals / Non-Goals

**Goals:**
- Make an invitation's initial status and dispatched-email content depend
  on `Company.auto_approve_pre_registered_visitors`, per the reported
  scenario.
- Add a manual-approval action for a `submitted` invitation that dispatches
  the QR-bearing email at that point, not before.
- Give an Admin a way to backfill a stale tenant's standard-role
  permissions against the current catalog, without a manual DB edit.

**Non-Goals:**
- Wiring `visitors/models.py::ApprovalWorkflowRule` (the per-visitor-
  category, multi-step, role-based approval chain) into this flow. That
  table is CRUD-only today with no runtime engine evaluating it against an
  invitation — building that engine is a materially larger effort than
  this change, and the reported scenario only ever references the
  company-wide auto-approve flag. Revisit once a real multi-step approval
  requirement is reported.
- A reject/decline action. Explicitly deferred per the proposal.
- Resyncing anything beyond the four real standard roles' permission sets
  (Visitor is intentionally always empty; custom roles are the tenant's own
  responsibility to manage via existing role CRUD).
- Auto-migrating a role's *removed* catalog permissions — the resync is
  additive-only (matching `seed_default_roles`'s existing union-merge
  behavior), never revoking a permission, even one no longer in a role's
  catalog default set.

## Decisions

### Decision 1: Resolve auto-approve once, at creation, from the Company singleton
`invitations/service.py::create_invitation` gains a lookup —
`CompanyRepository(tenant_db).get_singleton()` — read once per creation
call, right before constructing the `Invitation` row. `company is None or
not company.auto_approve_pre_registered_visitors` resolves to `status =
"submitted"`; otherwise `status = "approved"` with `approved_at = now`.

**Alternative considered**: re-check the flag lazily at read time (i.e.
every response computes status from the current flag). Rejected — an
invitation's approval state must be a stable, recorded fact of what
actually happened (a tenant flipping the setting later must not silently
retroactively change already-created invitations' status), consistent
with `submitted_at`/`expires_at` already being fixed at creation, not
recomputed.

### Decision 2: Split the single dispatch task into two, keyed by status
`invitations/tasks.py::send_visit_confirmation` is replaced by two Celery
tasks:
- `send_tracking_notification` — tracking ID + status only, no attachment.
  Enqueued when `create_invitation` resolves `status="submitted"`.
- `send_approval_notification` — tracking ID + QR PNG attachment (today's
  existing content). Enqueued when `create_invitation` resolves
  `status="approved"`, **and** by the new approve action once it flips a
  `submitted` invitation to `approved`.

Both share the existing `_dispatch`/idempotent-against-redelivery/retry-
with-backoff plumbing (`background-jobs.md` §2-3) — only the
subject/body/attachment construction differs, and only one of the two is
ever enqueued for a given state transition (never both).

**Alternative considered**: keep one task with an `include_qr: bool`
argument. Rejected — two small, named tasks read clearly as "which
notification is this" from a Celery monitoring dashboard/log line, versus
one task whose behavior silently branches on an opaque boolean argument;
this also matches `logging-observability.md`'s "log lines should carry
enough context to identify what happened" spirit for a background job.

### Decision 3: New `POST /invitations/{id}/approve`, gated by a new `invitations:approve` permission
Mirrors the existing `authorize_branch_id` pattern
(`org_structure/deps.py`) already used by `POST /invitations`: fetch the
invitation first (`InvitationRepository.get`), 404 if missing, then
`authorize_branch_id(tenant_db, user, "invitations:approve",
invitation.branch_id)`. `authorize_branch_id` itself 403s (not 404) when
the branch exists but the caller has no access to it, and 403s again if
the caller has branch access but lacks the named permission — the same
two-branch shape `POST /invitations` already gets from this exact
dependency when resolving a branch id it doesn't otherwise know from the
request. (An earlier draft of this design assumed a wrong-branch attempt
would 404 like the branch-scoped get/update/delete endpoints elsewhere in
`org_structure` do — verified against `authorize_branch_id`'s actual body
while implementing, and corrected: it 403s. Only a genuinely nonexistent
invitation id 404s, from this endpoint's own upfront fetch.) Then a
service-level state check: 409 if `invitation.status != "submitted"`.
On success: `status = "approved"`, `approved_at = now`, commit, enqueue
`send_approval_notification`, queue an audit-log background task
(`invitation_approved`, mirroring `invitation_created`'s existing
pattern).

`invitations:approve` is added to `auth/rbac_catalog.py::PERMISSION_CODES`
and granted by default to `admin`, `reception`, and `host` (the same three
roles `invitations:create` already grants to) — `security` stays
view-only, unchanged.

**Alternative considered**: reuse `invitations:create` instead of a new
permission. Rejected — creating and approving are different actions with
potentially different authorization intent (a reception desk that creates
walk-in registrations might not be trusted to approve someone else's
pre-registration); a dedicated permission costs nothing and is the
established pattern (`invitations:create`/`:view`/`:cancel` are already
separate codes for the same entity).

### Decision 4: `approved_at` as a new nullable column, via `alembic_tenant`
`Invitation` gains `approved_at: Mapped[datetime | None]`. Migration
authored in `alembic_tenant/versions/`, following `50d2e145f79f`'s already-
documented landmine: `op.add_column` does not honor `schema_translate_map`
the way `op.create_table` does, so the migration passes
`schema=op.get_context().version_table_schema` explicitly (same pattern as
every existing additive-column migration in this tree). Purely additive,
nullable, no backfill needed (every existing invitation is already either
implicitly "submitted-and-never-approved" — `approved_at` stays `NULL` — or
was created before this change existed at all, same result).

### Decision 5: Resync as its own endpoint, not a side effect of login or role read
`POST /auth/roles/resync-permissions`, gated by the existing
`roles:manage` permission (no new permission needed — this is a role-
management action). Service function `resync_role_permissions(tenant_db)`
snapshots each standard role's current permission-code set, calls the
existing `seed_default_roles(tenant_db)` (unmodified — its union-merge
logic is exactly what's needed here, just invoked again post-provisioning
instead of only at provisioning), then diffs each role's set against its
snapshot to report what was newly granted.

**Alternative considered**: run this automatically on every login (silently
resync in the background). Rejected — a permission grant is a security-
relevant, audit-worthy change; doing it invisibly on every login makes it
untraceable to a specific actor/action and risks surprising an admin who
deliberately narrowed a standard role's grants beyond the catalog default
(this resync only *adds* catalog-default permissions, but a silent
background job doing so is still a worse audit story than an explicit,
admin-triggered action). An explicit endpoint is also directly what fixes
the reported bug today, on demand, without waiting for the next login.

## Risks / Trade-offs

- [Risk] A tenant that deliberately narrowed Reception's grants below the
  catalog default (e.g. revoked `invitations:view` on purpose) would have
  that revocation silently undone by the resync, since the resync can't
  distinguish "never granted" from "deliberately revoked." → Mitigation:
  the resync is an explicit, admin-triggered action (Decision 5) — an
  admin who deliberately narrowed a standard role's grants simply doesn't
  run it, or re-narrows afterward; this is the same trade-off
  `seed_default_roles` already accepts at provisioning time (its own
  docstring: "a deliberate custom grant beyond the standard catalog
  survives" — the flip side, a deliberate *removal* below the standard
  catalog, isn't specially protected either, then or now).
- [Risk] Splitting one notification into two, keyed by status, means a
  client that previously always got a QR code in the single "visit
  confirmation" email now sometimes doesn't. → Mitigation: called out
  explicitly in `proposal.md`'s Impact section; this is the entire point
  of the reported scenario, not an accidental side effect.
- [Risk] `Company.get_singleton()` returning `None` (no Company profile
  configured yet) defaults to manual-approval — a tenant that hasn't
  configured its Company profile yet gets the more conservative behavior
  automatically, matching `auto_approve_pre_registered_visitors`'s own
  column default (`False`). No mitigation needed; this is the safe default.

## Migration Plan

- `alembic_tenant` migration adds `invitations.approved_at`; applied per
  tenant the same way every other tenant migration is
  (`platform/service.py::create_tenant`'s provisioning path, or a future
  "upgrade all tenants" ops task — `database-architecture.md` §5).
- No feature flag — both fixes ship together in one deploy. Existing
  invitations (all `submitted` or whatever status they already have) are
  unaffected; `approved_at` is `NULL` for all of them until acted on.
- Rollback is a plain revert of the code changes plus the migration's
  `downgrade()` (drops `approved_at`).

## Context

See `proposal.md` for motivation. The relevant existing machinery, confirmed
by reading the current code and specs before drafting this design:

- `invitations/service.py::_resolve_visit_detail_ids` resolves an optional
  client-supplied `hostId`/`hostNameOrEmail` at creation and, when it
  resolves, `_build_approval_steps` prepends a host-identified `stepOrder=0`
  `InvitationApprovalStep` ahead of the category's own configured
  `ApprovalWorkflowRule` chain.
- `approvals/service.py::delegate_step` already implements "reassign a
  pending step to a named person," including a host's blanket privilege to
  delegate any step, re-delegation/chaining, and an `invitations:approve-
  override` bypass. It dispatches no notification today.
- The five standard roles (`admin`, `reception`, `security`, `host`,
  `visitor`) are fixed and non-renameable, seeded/resynced idempotently by
  `auth/rbac_catalog.py::seed_default_roles`. `reception` already carries
  every invitation-related permission this change needs.
- `notifications/service.py::notify_role_at_branch` (push) already resolves
  "every user holding role R at branch B" via
  `UserRepository.list_user_ids_holding_role_at_branch`. Email has no
  equivalent role-fan-out primitive today, and no HTML template engine
  exists anywhere in the codebase (plain f-strings via `core/emailing.py`).

## Goals / Non-Goals

**Goals:**
- Make every new invitation's ownership step unconditional and role-owned,
  replacing the previous conditional host-identified step.
- Reuse `delegate_step` as the sole mechanism for assigning/reassigning the
  actual host, with one narrowly-scoped eligibility exception for the
  ownership step.
- Add one new endpoint for editing non-personal visit details, independent
  of host reassignment.
- Introduce a templated HTML email system without touching the interface
  contract call sites use to trigger email dispatch.

**Non-Goals:**
- Re-deriving or re-snapshotting the approval workflow when anything about
  an invitation changes post-creation (category stays locked; see the
  "Category Editability" resolved question in proposal.md's clarifying
  round).
- Per-tenant customizable email templates, or localization.
- Changing anything about how `ApprovalWorkflowRule` chains (`stepOrder` 1+)
  are configured or evaluated — only `stepOrder` 0's origin changes.
- A new role or permission-catalog entry — the tenant's default host role is
  configuration (defaults to `reception`), not a new standard role.

## Decisions

### D1: The default host role is a tenant-level setting, defaulting to `reception`, not a hardcoded name
Rather than hardcoding `"reception"` as a magic string wherever the owning
role is needed, add one nullable-with-default setting (e.g. on `Company` or
a small tenant-config table) resolving to the `Role` a tenant wants
invitations owned by. Default: the tenant's `reception` role. Every place
that needs "the owning role" (snapshot logic, push/email fan-out,
`relevantToMe`, the delegate-eligibility exception) resolves it through one
function, not a string literal repeated in five files.
- **Alternative considered**: hardcode `"reception"` by name everywhere.
  Rejected — a tenant that renames/repurposes roles (the catalog allows
  custom roles alongside the five standard ones) would have no way to point
  ownership at a different role without a code change, and several
  requirements already carry an implicit "unless reconfigured" escape hatch
  in their text (e.g. the `admin`-role-gets-no-push exclusion) that a
  hardcoded name can't honor consistently.

### D2: Host resolution happens exclusively via `delegate_step` on `stepOrder` 0, never a second code path
`PATCH /invitations/{id}/edit` explicitly rejects `hostId`/`hostNameOrEmail`
(see the `invitations` spec's "Authorized Caller Edits Non-Personal
Invitation Details"). The only way `Invitation.host_id` changes after
creation is `delegate_step` on `stepOrder` 0, which now additionally writes
`host_id`/`host_name_or_email` in the same transaction as recording the
delegation.
- **Alternative considered**: let the new edit endpoint also accept
  `hostId` as a convenience, internally routing to the same delegation
  logic. Rejected in the proposal's clarifying round — two entry points
  for "who is the host" (one that goes through step-eligibility checks, one
  that wouldn't) is exactly the kind of inconsistency this codebase's
  repository/service layering elsewhere avoids; a caller who wants to
  reassign the host calls the delegate endpoint, full stop.

### D3: The `stepOrder` 0 delegate-eligibility exception is scoped narrowly, by step position, not by role identity
`approvals/service.py::delegate_step`'s existing eligibility check ("named
delegate must hold the step's `approverRoleId` role") is bypassed only when
the step being delegated is `stepOrder` 0 — not "whenever the step's role
happens to be the tenant's configured default host role." This matters
because a category's own `ApprovalWorkflowRule` chain could theoretically
also configure a later step (`stepOrder` 1+) for that same role (e.g. a
tenant reusing `reception` for a second-level check) — that later step's
delegate SHOULD still be required to hold the role, since it's a genuine
approval-authority check, not an ownership handoff.
- **Alternative considered**: key the exception off "is this step's role the
  tenant's default host role" instead of "is this `stepOrder` 0." Rejected —
  conflates two different concepts (which step is the ownership step vs.
  which role a step happens to name) and would produce surprising behavior
  if a tenant ever reuses the role elsewhere in its configured chain.

### D4: Email templating is a rendering step inserted before the existing `EmailSender` interface, not a parallel dispatch path
`core/emailing.py`'s `EmailSender` interface (`send(to, subject, body,
attachment=None)`) already documents itself as "a new implementation, not a
call-site change" for provider swaps. Templates render to
`(subject, html_body, text_body)` and get handed to a slightly extended
`send()` (adding an optional `html_body` alongside the existing plain
`body`, used as the multipart alternative) — call sites in
`invitations/tasks.py` change from building an f-string to calling
`render_template(name, context)`, but nothing about *how* the result gets
sent changes.
- **Alternative considered**: a wholly separate "templated email" sender
  class parallel to today's plain-text one. Rejected — every notification
  eventually needs templating (per the proposal), so a parallel path would
  just be dead code once the migration finishes; better to extend the one
  interface in place.

### D5: Template rendering failure degrades to a minimal plain-text email, never silently drops the notification
Per the `email-notifications` spec's "Template Rendering Failure Falls Back
to a Minimal Plain-Text Email" — a missing template context field (e.g. a
new template referencing a host field that happens to be null in an
edge case not yet handled) must not turn into "no email sent at all,"
which would be a regression from today's simple-but-reliable f-strings.

## Risks / Trade-offs

- **[Risk]** Every existing invitation created before this change ships has
  whatever `stepOrder` 0 shape it was snapshotted with (host-identified or
  absent) — the new unconditional-role-step behavior only applies to
  invitations submitted after deployment. → **Mitigation**: no migration of
  historical rows is attempted; `delegate_step`'s existing per-step logic
  already branches on whether a step is host- or role-identified, so
  in-flight invitations keep working under their original shape without any
  special-casing.
- **[Risk]** Breaking API change (`hostId`/`hostNameOrEmail` no longer
  drive routing) ships before both the React portal and Flutter app have
  stopped depending on host-driven behavior. → **Mitigation**: the fields
  are accepted-but-ignored rather than rejected (see "Visit Details
  Optionally Accept Catalog IDs Alongside Free Text"), so an un-updated
  client does not start failing outright — it just stops getting the
  behavior it used to request. Coordinate the web-app deploy from the
  companion `VMMS_WEB` change to land no later than this one; flag Flutter
  separately since it's a different repo/team not covered by this change.
- **[Risk]** A tenant with no active user holding the default host role at
  a given branch would have an invitation stuck with nobody able to act on
  `stepOrder` 0 except an `invitations:approve-override` holder. →
  **Mitigation**: this is an existing class of risk (a role-identified step
  with zero role-holders at a branch is already possible today for any
  configured `ApprovalWorkflowRule` step) — not new to this change, and
  already has the override escape hatch. Out of scope to add branch-level
  "must have at least one reception-role user" validation here.
- **[Trade-off]** Adding `jinja2` is a new dependency for a system that
  otherwise keeps its dependency surface deliberately small
  (`project-rules.md`). Accepted — hand-rolled HTML string composition for
  seven-plus notification types would be worse for both correctness (escaping)
  and maintainability than one well-understood templating library already
  battle-tested inside the FastAPI ecosystem.

## Migration Plan

1. Ship the `email-notifications` capability (templates + rendering step)
   first, as a pure refactor of existing plain-text bodies into templates
   with identical *information content* — independently testable/deployable
   without touching host/role logic at all.
2. Ship the default-host-role config + unconditional `stepOrder` 0 snapshot
   change (`approvals`), the `delegate_step` eligibility exception, and the
   host-resolution-on-delegate behavior together, since they're one
   cohesive unit of behavior.
3. Ship the `invitations:edit` endpoint (independent of steps 1-2; can land
   in parallel).
4. Ship the request-schema change that stops accepting `hostId`/
   `hostNameOrEmail` at creation last, once the web app (companion change)
   is ready to stop sending them — this is the one genuinely breaking step,
   and the accepted-but-ignored behavior (D-level detail in "Visit Details
   Optionally Accept Catalog IDs Alongside Free Text") means it's safe to
   flip even slightly ahead of the web app if needed.
- **Rollback**: each of the four steps above is independently revertible;
  no destructive data migration is involved (no column removed, no historical
  row rewritten), so rollback is a straightforward revert-and-redeploy at any
  point in the sequence.

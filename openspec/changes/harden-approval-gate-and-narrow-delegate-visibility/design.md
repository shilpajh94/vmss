## Context

`_relevant_to_me_filter` (`src/vmss_api/invitations/repository.py:29`) is a
pure, synchronous query-builder taking only `user_id` — it has no DB access
of its own, and is called from `InvitationRepository.list_page` (async, has
`self.session`), which in turn is called from
`invitations/service.py::list_invitations_page` (also async, has
`tenant_db`). Its current clause (c) is built as an `exists()` subquery
joining `UserBranchRole` to the invitation's current pending step's
`approver_role_id` — it does not distinguish the tenant's default host role
from any other role-identified step.

Separately, `org_structure/service.py::get_default_host_role(tenant_db) ->
Role` already resolves the tenant's default host role (`Company.
default_host_role_id`, falling back to the seeded `reception` role) —
`invitations/service.py` already imports and calls it once, at submission
time (`src/vmss_api/invitations/service.py:40,489`), so the cross-feature
import is already sanctioned for this module.

The approvals half of this change (the new ordering-guarantee requirement)
adds no new query or model — `delegate_step`/`approve_step`/`reject_step`
already call `_resolve_current_step` + `_require_is_current` before any
authorization check, which is exactly what the new requirement documents.
That half is pure test/spec hardening.

See proposal.md for why the visibility narrowing and the permanent
Reception clause are wanted.

## Goals / Non-Goals

**Goals:**
- Make `_relevant_to_me_filter` resolve visibility per the modified spec:
  clause (c) requires the step to be undelegated; a new clause (e) grants
  every default-host-role holder permanent, unconditional visibility.
- Keep `_relevant_to_me_filter` a single SQL query (no per-invitation loop),
  consistent with `query-performance.md` §1/§2.
- Add regression tests locking in the existing ordering guarantee in
  `approvals/service.py`, with no production code change there.

**Non-Goals:**
- No change to `Company.default_host_role_id` resolution/fallback logic
  itself (`get_default_host_role` is reused as-is).
- No change to the branch-scoped admin listing
  (`GET /invitations` without `relevantToMe`), to `GET /invitations/{id}`
  detail visibility, or to any RBAC permission catalog entry.
- No change to how a delegate is chosen or named (still a manual, specific
  person per delegate call) — no workload/auto-assignment algorithm.
- Does not touch or coordinate with the separately in-flight
  `delegator-retains-invitation-visibility` change (a distinct, additive
  clause (e)-numbered-differently-there for whoever personally delegated a
  step); the two changes touch the same requirement's prose but not the
  same clause, and will need a straightforward text merge whichever
  archives second — noted here so that merge isn't a surprise.

## Decisions

### Decision 1: Resolve the default host role's id in the service layer, pass it down as a plain UUID

`_relevant_to_me_filter` gains a required `default_host_role_id:
uuid.UUID` parameter instead of reaching for the DB itself. `list_page` and
`list_invitations_page` thread it through unchanged otherwise.
`invitations/router.py`'s `relevantToMe` handler resolves it once via
`org_structure.service.get_default_host_role(tenant_db)` and passes
`.id` down, exactly mirroring the existing call at submission time
(`invitations/service.py:489`).

**Alternatives considered:**
- *Make `_relevant_to_me_filter` async and resolve the role inside it* —
  rejected: every other filter-builder in this file
  (`_branch_filter`, `_order_clause`) is a plain sync function; making just
  this one async for a single extra lookup is inconsistent and forces
  `list_page` to await a nested call it doesn't otherwise need visibility
  into.
- *Hardcode the `reception` role name in the query* — rejected: bypasses
  `Company.default_host_role_id` entirely, breaking tenants that have
  reconfigured their owning role (exactly the case `get_default_host_role`
  exists to handle).

### Decision 2: Clause (e) matches on `UserBranchRole.role_id`, not on any step data

Clause (e) is independent of `InvitationApprovalStep` entirely — it is
`exists(select from UserBranchRole where role_id = default_host_role_id and
user_id = :user_id and (branch_id = Invitation.branch_id or branch_id IS
NULL))`, correlated only to `Invitation.branch_id`. This mirrors the
existing branch-or-company-wide pattern clause (c) already uses, but with
no join to approval steps at all, so it naturally applies "regardless of
current step, delegation state, or invitation status" per the spec, with
no extra `OR`s needed to cover status transitions.

### Decision 3: Clause (c) gains an explicit "no delegate assigned" predicate on the correlated step

The existing `current_role_holder` `exists()` subquery adds one predicate:
`current_step.delegated_to_user_id.is_(None)`. This is the entire code
change needed for the narrowing behavior — once a step is delegated, the
correlated subquery for any caller who only matches by role (not as the
delegate, host, or a past actor) simply stops matching.

### Decision 4: The approvals ordering guarantee ships as tests only, no production diff

`delegate_step`/`approve_step`/`reject_step` already call
`_resolve_current_step` + `_require_is_current` unconditionally, before
any authorization branch (resolved-host, override, role-match, or
previous-step-approver). Tracing each call site confirms the guarantee
already holds; this change adds `approvals/tests.py` cases exercising it
directly (delegate-then-attempt-next-step, override-permission-attempt-
next-step) rather than touching `service.py`. If a future reviewer wants to
double check: `_require_is_current` runs before the `is_resolved_host` /
`was_previous_step_approver` / override checks in `delegate_step`
(`src/vmss_api/approvals/service.py:298-319`), and before
`_authorize_step_action` in `approve_step`/`reject_step`
(`:178-180`, `:226-228`).

## Risks / Trade-offs

- **[Risk]** Narrowing clause (c) is a **BREAKING** behavior change for any
  existing UI/client that relies on seeing a delegated invitation in
  `relevantToMe` as a non-default-host role-holder → **Mitigation**: this is
  an explicit, confirmed product decision (see proposal.md); no API
  contract (params/response shape) changes, so clients don't need code
  changes, only for their own users to notice the narrower result set.
  Flag in `docs/features/invitations.md` per `api-conventions.md` §2 since
  it changes an existing endpoint's observable behavior for the same
  request.
- **[Risk]** A tenant with no `Company` row configured yet (pre-provisioning)
  would make `get_default_host_role` 500 if called from the `relevantToMe`
  path → **Mitigation**: `GET /invitations` already requires an
  authenticated, branch-scoped user, which in turn requires the tenant to
  be fully provisioned (seeded roles, including `reception`); this is the
  same precondition `invitations/service.py:489` already relies on at
  submission time, so no new failure mode is introduced.
- **[Risk]** Threading `default_host_role_id` through `list_page`'s
  signature touches a widely-called repository method →
  **Mitigation**: it's a required keyword-only parameter alongside the
  existing ones, and only the `relevantToMe` branch inside `list_page`
  actually uses it (the branch-scoped listing path ignores it), so the
  blast radius is one `if` branch, not every caller's logic.

## Migration Plan

No data migration. Deploy is a plain code + spec update: update
`_relevant_to_me_filter`'s signature and its two callers
(`list_page`, `list_invitations_page`, `router.py`'s `relevantToMe` handler),
update tests, update the two spec files. Rollback is a plain revert — no
persisted state depends on the new clause shape.

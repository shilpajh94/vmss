## Why

Two gaps in the reception → delegation → visibility flow need closing.
First, nothing in `specs/approvals/spec.md` states, as its own testable
requirement, that a step can only ever be delegated once every step ahead of
it in the chain has actually been acted on — the guarantee exists today only
as an emergent property of the strict-current-step check (`_require_is_current`
in `delegate_step`), scattered across several requirements' prose. That makes
it easy for a future change to `delegate_step` (e.g. loosening the
resolved-host clause) to silently reopen "delegate a later step before
Reception's own `stepOrder` 0 step is approved" without any test catching it.
Second, and independently, `relevantToMe`'s clause (c) currently broadcasts a
current, role-identified step to *every* holder of that role for as long as
it's current — including after it has been delegated to one specific person.
Reception has confirmed that once a step is delegated to someone, every other
holder of that step's role should stop seeing the invitation (only the
delegate should); Reception itself is the one exception, since Reception owns
the front-office intake for every invitation and needs permanent visibility
regardless of stage or delegation.

## What Changes

- **BREAKING**: Narrow `relevantToMe` clause (c) so that once ANY
  role-identified step (`stepOrder` 0 or later) has a delegate assigned,
  that step's role-holders other than the delegate no longer see the
  invitation via `relevantToMe=true` on that basis. A caller who is not the
  delegate, the resolved host, or someone who personally acted on a step now
  loses visibility the moment that step is delegated, instead of keeping it
  until the step is approved/rejected. This reverses the specific "a
  role-holder keeps seeing the invitation once someone else's delegation is
  assigned" scenario added by `reception-retains-visibility-and-delegation-
  after-own-step`.
- Add a new, permanent visibility clause: every user holding the tenant's
  default host role (e.g. `reception`) at an invitation's branch or
  company-wide sees that invitation via `relevantToMe=true` for its entire
  lifecycle, regardless of the invitation's current step, delegation state,
  or overall status. This replaces clause (c)'s role-broadcast behavior for
  the default host role specifically (which is unaffected by the narrowing
  above) while every other role-identified step's visibility narrows per the
  bullet above.
- Add an explicit, standalone requirement to `specs/approvals/spec.md`
  stating and testing the ordering guarantee already enforced by
  `_require_is_current`: a step at `stepOrder` N cannot be delegated (or
  approved/rejected) while any step at a lower `stepOrder` is still
  `pending` — in particular, no step beyond the `stepOrder` 0 ownership step
  can be delegated until that step has been approved, whether by a Reception
  role-holder directly or by whoever Reception delegated it to. This adds
  regression coverage for a guarantee that already holds in code today; it
  is not a behavior change to `delegate_step`, `approve_step`, or
  `_resolve_current_step`.
- No change to how a delegate is chosen (`POST
  /invitations/{id}/approval-steps/{stepId}/delegate` still names a specific
  person manually) — "workload" is a factor in the human decision of who to
  name, not a new automated assignment algorithm.
- No change to the unrelated, separately in-flight
  `delegator-retains-invitation-visibility` change (adding permanent
  visibility for whoever personally delegated a step) — that change adds a
  new clause (e) and does not touch clause (c); it composes with this one
  without conflict.

## Capabilities

### New Capabilities

(none)

### Modified Capabilities

- `invitations`: the `relevantToMe` requirement's clause (c) is narrowed to
  stop applying once a step has a delegate assigned, and a new permanent,
  role-wide visibility clause is added for the tenant's default host role.
- `approvals`: a new requirement states and tests the existing
  lower-`stepOrder`-must-be-non-pending ordering guarantee for delegation
  (and approval/rejection) as its own explicit, regression-tested rule
  rather than only implicit in `delegate_step`'s and `approve_step`'s prose.

## Impact

- `src/vmss_api/invitations/repository.py::_relevant_to_me_filter` — replace
  clause (c)'s unconditional per-role-while-current match with (i) a
  delegate-not-yet-assigned condition for non-default-host-role steps, and
  (ii) an unconditional OR clause matching any branch-scoped (or
  company-wide) holder of the tenant's default host role, independent of
  step/status.
- `src/vmss_api/invitations/tests.py` — update/replace
  `test_list_invitations_relevant_to_me_...` scenarios asserting the old
  "role-holder keeps seeing invitation once delegated" behavior; add
  coverage for the new default-host-role permanent clause and the narrowed
  non-default-role behavior.
- `src/vmss_api/approvals/service.py` — no functional change; `delegate_step`,
  `approve_step`, `reject_step`, `_resolve_current_step`, and
  `_require_is_current` already enforce the ordering guarantee this change
  documents.
- `src/vmss_api/approvals/tests.py` — add explicit regression tests for the
  new ordering requirement (attempting to delegate/approve/reject a
  `stepOrder` N step while `stepOrder` < N is still pending is rejected with
  409, including via the resolved-host and override-permission bypasses).
- `openspec/specs/invitations/spec.md` and `openspec/specs/approvals/spec.md`
  — updated per the delta specs.
- No API contract change (same endpoints, same request/response shapes), no
  migration, no permission catalog change.

## Why

`GET /invitations?relevantToMe=true` is the personal worklist a role-holder
(e.g. Reception) uses to find invitations they need to act on or track. Today,
someone who merely *delegates* one of an invitation's approval steps (without
personally approving/rejecting it) only stays visible in that worklist while
their role's step is still the current pending one (clause "c" of
`_relevant_to_me_filter`). Once the delegate acts and the workflow advances to
a different step/role, the delegator loses visibility entirely — even though
they were the one who routed the request in the first place. Reception has
confirmed this is wrong: whoever delegates a step should keep seeing that
invitation for its entire lifecycle, the same permanence guarantee already
given to someone who personally acted on a step (clause "d").

## What Changes

- Add a new, permanent visibility clause (e) to `relevantToMe`: the caller who
  delegated any of the invitation's approval steps
  (`InvitationApprovalStep.delegated_by_user_id == caller`) keeps seeing that
  invitation via `relevantToMe=true` for its entire lifecycle, regardless of
  whether that step is later approved/rejected by someone else, or the
  workflow advances past it — mirroring clause (d)'s permanence, not clause
  (c)'s current-step-only visibility.
- Correct the existing test
  `test_list_invitations_relevant_to_me_role_holder_loses_visibility_once_step_acted_on`
  (`src/vmss_api/invitations/tests.py:1923`), which currently asserts the
  opposite (that a delegator loses visibility once their delegated step is
  acted on by someone else) — that assertion described the pre-change
  behavior and must be updated/renamed to assert the new permanent-visibility
  outcome instead.
- No change to the underlying RBAC permission model, branch-scoped
  `invitations:view` listing, or the `GET /invitations/{id}` detail endpoint —
  this is scoped entirely to the `relevantToMe` worklist query.

## Capabilities

### New Capabilities

(none)

### Modified Capabilities

- `invitations`: the `relevantToMe` requirement gains a fifth visibility
  clause (delegator permanence) and the existing "loses visibility once
  acted on" scenario is corrected to reflect that a delegator's visibility no
  longer depends on their delegated step remaining current.

## Impact

- `src/vmss_api/invitations/repository.py::_relevant_to_me_filter` — add the
  new OR clause against `InvitationApprovalStep.delegated_by_user_id`.
- `src/vmss_api/invitations/tests.py` — update/replace the test asserting the
  old drop-off behavior; add coverage for the new permanent-visibility rule.
- `openspec/specs/invitations/spec.md` — update the `relevantToMe` requirement
  and its scenarios to describe clause (e) and correct the now-inaccurate
  "loses visibility" scenario for delegators.
- No API contract change (still `GET /invitations?relevantToMe=true`, no new
  query params or response fields), no migration, no permission catalog
  change.

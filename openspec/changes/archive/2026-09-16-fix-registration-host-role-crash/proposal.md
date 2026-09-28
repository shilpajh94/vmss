## Why

A visitor registration submission (individual, via `POST /registrations/
walk-in`) failed with a raw 500 at the review/submit step. Investigation
found the failure is not in form-builder rendering — zero-field custom
steps and empty optional sections (Vehicle Info, Carried Items) are already
handled correctly end to end — but in the shared `create_invitation` path
every registration (walk-in, staff pre-registration, invitation) goes
through, which has three related, previously-undertested gaps around
form-builder-driven registration:

1. `org_structure/service.py::get_default_host_role` (lines 252-276)
   deliberately raises `HTTPException(500, ...)` when a tenant's `reception`
   role can't be resolved — a real, reachable crash site in this exact
   call chain (`create_invitation` calls it unconditionally for every
   non-auto-approved submission), but with **zero test coverage** and no
   corresponding scenario in the `approvals`/`invitations` capability specs,
   so the documented-in-code intent ("a provisioning bug, not a
   client-facing condition") was never verified or specified. Standard-role
   protection (`auth/service.py`'s `update_role`/`delete_role`) already
   blocks renaming or deleting `reception` through the normal admin UI, so
   this is most likely reachable only via a provisioning gap (a tenant whose
   seeding never ran or partially failed) rather than an admin action — but
   an untested crash path that a provisioning edge case can still reach is
   worth closing regardless of how the specific incident's tenant got there.
2. The public walk-in registration wizard resolves its own `branchId`
   client-side to fetch/render that branch's published form-builder config,
   but `POST /registrations/walk-in` never receives a branch id — the server
   independently resolves the branch via device credential or a
   server-configured default (`registrations/deps.py`). If those two
   resolutions diverge (the wizard rendered branch A's config, the server
   resolves and enforces branch B's), whatever they disagree on is enforced
   silently against the wrong config, with no diagnostic trail distinguishing
   this from any other validation failure.
3. `form_builder/service.py::create_field` only enforces field-key
   uniqueness within one step; `form_builder/validation.py`'s
   `custom_fields_for_invitation_scope` then merges every step's fields into
   one flat `fields_by_key` map when validating a submission, so two fields
   sharing a key across different steps silently validate a submitted value
   against whichever field the merge happened to keep, rather than being
   prevented at field-creation time.

None of these three is confirmed as *the* exact line that produced the
screenshot's 500 (no server traceback was available to pin it precisely),
but all three are real, reachable gaps in the same registration-submission
path the bug report is about, found together during the same investigation,
and all three currently have no test coverage — which `testing-standards.md`
treats as an incomplete feature, not an acceptable gap.

## What Changes

- Add a scenario to the `approvals` capability spec documenting the
  already-implemented "no resolvable default host role" failure mode
  (currently code-only, undocumented in specs) and add the missing test
  exercising it (a tenant whose `reception` role is absent).
- Add a scenario to the `registrations` capability spec requiring that a
  walk-in registration is validated and persisted against the
  server-resolved branch's published form-builder configuration — never a
  client-supplied or client-assumed one — and that a resulting rejection
  logs which branch was actually enforced, so a client/server branch
  divergence is diagnosable from the log rather than indistinguishable from
  any other validation error.
- Add a new `form-builder` capability spec (none exists today, despite the
  feature having shipped) documenting field-key uniqueness across a
  branch's entire active form, not just within one step, and change
  `create_field` to enforce it at that scope.
- Add missing test coverage per `testing-standards.md` §2: submitting a
  registration through a genuinely new custom step (not just adding fields
  to an existing seeded step), and a walk-in registration test exercising
  the server-resolved-default-branch path end to end.

## Capabilities

### New Capabilities
- `form-builder`: branch-scoped registration-step/custom-field
  configuration and its constraints on submitted registration/invitation
  data — no spec exists for this capability today even though it has
  shipped (two prior commits: "add branch-scoped form builder...", "extend
  form builder with step ordering fixes and generic custom fields").

### Modified Capabilities
- `approvals`: document the default-host-role-unresolvable failure mode of
  "Submission Snapshots the Category's Workflow Plus an Unconditional
  Ownership Step."
- `registrations`: require walk-in registration submission to validate
  against the server-resolved branch's form-builder config, with
  distinguishing log output on a client/server branch divergence.

## Impact

- `src/vmss_api/org_structure/service.py` (`get_default_host_role`) — no
  behavior change, adds a spec/test.
- `src/vmss_api/registrations/service.py` and/or `deps.py` — diagnostic
  logging for branch/form-config divergence.
- `src/vmss_api/form_builder/service.py` (`create_field`) and
  `form_builder/validation.py` — field-key uniqueness scope change.
- `src/vmss_api/invitations/tests.py`, `src/vmss_api/registrations/tests.py`,
  `src/vmss_api/form_builder/tests.py`, `src/vmss_api/org_structure/tests.py`.
- No frontend changes. The layout/scroll/refresh issues reported alongside
  this error are unrelated frontend gaps, addressed by the paired change
  `fix-form-builder-layout-and-refresh-gaps` in `VMMS_WEB`.

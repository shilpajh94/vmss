## Context

`create_invitation` (`invitations/service.py`) is the single path every
registration/invitation flows through — staff pre-registration, walk-in
(`registrations/service.py::create_walk_in_registration`), and the standard
invitation-creation endpoint. Two things confirmed during investigation, so
this design doesn't need to invent new plumbing for them:

- `resolve_effective_form(tenant_db, redis, tenant_id=tenant.id,
  branch_id=branch_id)` (`invitations/service.py:354-356`) already validates
  against the server-resolved `branch_id` — the one `registrations/deps.py`
  resolved via device credential or the default-tenant/default-branch
  fallback, never a client-supplied value. The enforcement-target
  requirement in `specs/registrations/spec.md` is therefore already met by
  existing code; what's missing is a diagnostic log on failure, not a
  behavior change.
- `tenant_id` (and, on the walk-in path, `branch_id`) are already bound into
  `structlog`'s contextvars before `create_invitation` runs
  (`core/tenancy.py:131` for authenticated requests, `registrations/
  deps.py:105,155` for device/default-fallback resolution) — see
  `logging-observability.md` §1. `get_default_host_role`'s existing
  `logger.error("default_host_role_not_seeded")` (`org_structure/
  service.py:271`) already inherits `tenant_id` for free; no code change
  needed there either, only the spec/test coverage that was missing.

## Goals / Non-Goals

**Goals:**
- Close the three gaps found together during this investigation, all in the
  shared registration-submission path, with the smallest change that makes
  each one specified and tested.
- Make a future client/server branch-config divergence distinguishable from
  an ordinary validation error in the logs, without changing what status
  code or message the caller receives.

**Non-Goals:**
- Reproducing or confirming the exact line that produced the screenshot's
  500 — no server traceback was available (see proposal.md), so this change
  hardens the three reachable gaps found rather than claiming to have fixed
  "the" bug. If the same error recurs, the new logging this change adds
  (branch id on a config-mismatch rejection) should make the next
  occurrence diagnosable.
- Changing `get_default_host_role`'s behavior (still 500 + `ERROR` log) —
  that's a deliberate, already-correct design decision
  (`role-based-invitation-workflow/design.md` Decision D1); this change
  only specifies and tests it.
- Any change to the public wizard's own branch resolution in `VMMS_WEB` —
  out of scope for this backend change; if the wizard's client-side branch
  resolution needs to change, that's a separate, frontend-side proposal.
- Retroactively fixing any already-created field-key collision in existing
  tenant data — the uniqueness check only prevents new collisions from
  `create_field` going forward.

## Decisions

- **No behavior change for `get_default_host_role`; add spec + test only.**
  The code's own docstring already states the intended contract correctly.
  The gap was that `approvals`/`invitations` specs never captured it and no
  test exercised it — both closed by `specs/approvals/spec.md`'s new
  requirement and a new test seeding a tenant with `reception` deleted
  (bypassing the API's own rename/delete protection directly at the
  repository/fixture level, since the protection makes this unreachable via
  the API itself — the test needs to simulate the provisioning-gap
  scenario, not go through `DELETE /roles/{id}`).
- **Add a log line on custom-field/consent/required-field validation
  failure identifying the enforced branch, not a new validation rule.**
  `form_builder/validation.py`'s `validate_custom_field_values` (and the
  required-field/consent-key checks around it in `invitations/
  service.py:354-460`) currently raise `HTTPException(422)` with no log at
  all. Add one `logger.warning` call at the point of rejection, carrying
  the branch id already in scope — `branch_id` is already bound into
  contextvars for the walk-in path, so this is one explicit field, not new
  plumbing. Alternative considered: reject earlier with a distinct error
  code if the client sends a branch hint that disagrees with the resolved
  branch. Rejected — the request payload deliberately carries no branch
  field at all (`registrations/spec.md`'s existing "Walk-in registration
  accepts the same visit-record contract" requirement), so there is no
  client-sent branch value to compare against; the visible symptom is
  purely "this submission didn't match this branch's config," which the log
  line captures without needing a new field on the wire.
- **Field-key uniqueness check moves from per-step to per-branch's active
  form, enforced in `create_field`.** Alternative considered: leave
  creation-time scope alone and instead make
  `custom_fields_for_invitation_scope`'s merge order deterministic (e.g.,
  first-defined-wins) so a collision is at least consistent rather than
  arbitrary. Rejected — that papers over silently-wrong validation instead
  of preventing the collision from being created, and an admin configuring
  two steps with an accidentally-shared key gets no signal anything is
  wrong until a visitor's submission is mis-validated against the wrong
  field's type/options. Rejecting at `create_field` time gives the admin
  the same immediate, correctable signal the existing per-step check
  already gives for an in-step collision.
- **New `form-builder` capability spec is scoped to only this requirement,
  not a full retroactive spec of the whole feature.** The feature has
  already shipped without a spec; documenting field-key uniqueness here
  (the one behavior this change touches) is enough for this bug-fix change.
  Writing a complete baseline spec for the whole form-builder feature is a
  separate, larger documentation task, flagged in proposal.md as an
  existing gap rather than undertaken here.

## Risks / Trade-offs

- [Risk] The `get_default_host_role` test needs to put a tenant schema into
  a state the product's own API can't produce (a missing `reception` role),
  which means constructing that state directly via the test fixture/
  repository layer → Mitigation: this is explicitly sanctioned by
  `testing-standards.md` §1's factory-based test-data approach; the test
  documents in a comment why it bypasses the API-level protection, so a
  future reader doesn't mistake it for a reachable-via-API scenario.
- [Risk] The per-branch field-key uniqueness check could reject a field key
  an existing tenant already has duplicated across two steps, on their next
  *new* field creation for an unrelated key, if the check is naively
  implemented as "no other key in the branch can equal this one" applied
  too broadly → Mitigation: the check only runs against the new field's own
  key at creation time; it does not re-validate every existing field on the
  branch, so it cannot reject unrelated creates due to a pre-existing
  collision elsewhere.
- [Trade-off] The branch-config-mismatch logging is diagnostic only — it
  does not change the 422 the caller receives, so if that mismatch is in
  fact the cause behind the original screenshot's 500 (not 422), this
  change would not have prevented that specific incident. This is accepted
  because no traceback was available to confirm that theory (see proposal.md
  and the Goals/Non-Goals above); the logging still makes the next
  occurrence — 422 or 500 — diagnosable from server logs alone.

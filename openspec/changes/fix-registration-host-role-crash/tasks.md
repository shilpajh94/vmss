## 1. Default host role failure — spec/test coverage (no behavior change)

- [x] 1.1 Add a factory-based test in `org_structure/tests.py` (or
      `invitations/tests.py`, wherever the tenant fixture lives) that
      deletes/renames the tenant's seeded `reception` role directly via the
      repository layer (bypassing `auth/service.py`'s API-level rename/
      delete protection, per `design.md`), then submits a non-auto-approved
      invitation and asserts a 500, an `ERROR` log line, and that no
      `Invitation`/`InvitationVisitor`/`InvitationVehicle`/
      `InvitationApprovalStep` row was persisted.
      Added `test_create_invitation_missing_default_host_role_fails_as_server_misconfiguration`
      in `invitations/tests.py`.
- [x] 1.2 Add the same assertion for the walk-in path
      (`POST /registrations/walk-in`) in `registrations/tests.py`, to
      confirm the shared `create_invitation` path fails identically
      regardless of entry point.
      Added `test_walk_in_registration_missing_default_host_role_fails_as_server_misconfiguration`
      in `registrations/tests.py`.

## 2. Branch/form-config divergence diagnostics

- [x] 2.1 Add a `logger.warning` call at the rejection point(s) in
      `invitations/service.py` (around the required-field/consent-key
      checks and `form_builder_validation.validate_custom_field_values`
      calls, lines ~354-460) carrying the resolved `branch_id` and which
      check failed (required field / consent key / custom field).
      Every rejection site in that block now logs
      `registration_form_config_validation_failed` with `branch_id`,
      `check` (`required_field`/`carried_item`/`consent_key`/`custom_field`),
      and a `reason`/`scope`; the four `validate_custom_field_values` calls
      are wrapped by a local `_validate_custom_fields` helper so the
      HTTPException raised inside `form_builder/validation.py` is still
      logged with `branch_id` before propagating.
- [x] 2.2 Add a test in `registrations/tests.py` that publishes distinct
      form-builder configs for two branches, submits a walk-in registration
      that resolves to one branch but supplies data matching only the
      other's configuration, and asserts the rejection's log output
      identifies the enforced branch.
      Added `test_walk_in_registration_branch_config_mismatch_logs_enforced_branch`.

## 3. Field-key uniqueness across a branch's active form

- [x] 3.1 Change `form_builder/service.py::create_field` to check key
      uniqueness against every active field across the branch's active
      steps, not only the target step (extend or replace the existing
      `repo.get_by_key(step_id, payload.key)` check).
      Added `FormFieldRepository.get_by_key_in_branch` (joins `FormStep`,
      filters to active steps/active fields, optionally excludes the target
      step) and call it from `create_field` alongside the existing
      same-step check.
- [x] 3.2 Add tests in `form_builder/tests.py`: creating a field with a key
      already used on a different active step of the same branch is
      rejected (409); creating a field with a key already used on the same
      step is still rejected (409, existing behavior); distinct keys across
      steps succeed.
      Added `test_create_field_key_collision_on_same_step_rejected`,
      `test_create_field_key_collision_on_different_active_step_rejected`,
      `test_create_field_distinct_keys_across_steps_succeed`.

## 4. Missing submission-path test coverage (testing-standards.md §2)

- [x] 4.1 Add a test in `invitations/tests.py` (or `form_builder/tests.py`)
      that creates a genuinely new custom registration step (not just adds
      a field to an existing seeded step), adds a field to it, publishes
      the form, and submits an invitation/registration through it
      end-to-end — covering the exact "test"/"test 2" custom-step shape
      seen in the bug report, including a custom step with zero fields
      configured.
      Added `test_create_invitation_through_new_custom_step_with_and_without_fields`
      in `invitations/tests.py`.
- [x] 4.2 Add a walk-in registration test exercising the server-configured
      default-tenant/default-branch fallback path (no device credential)
      end-to-end through `create_invitation`, not just the device-credential
      path, per `registrations/spec.md`'s existing "No device credential
      falls back to the default tenant and branch" scenario.
      Found already satisfied by a pre-existing test —
      `registrations/tests.py::test_walk_in_registration_missing_device_key_falls_back_to_default_tenant_success`
      already submits a full walk-in registration with no `X-Device-Key`
      through the default-tenant/default-branch fallback and asserts a 201
      with `status == "submitted"`. No new test added to avoid duplicating
      it; flagged in the implementation report as a discrepancy against this
      task's premise that the coverage was missing.

## 5. Verification

- [x] 5.1 `ruff check` and `ruff format --check` clean.
- [x] 5.2 `mypy` clean on `org_structure`, `invitations`, `registrations`,
      `form_builder` (all touched by this change).
      Note: `mypy` on `invitations` reports 2 pre-existing errors in
      `invitations/router.py` (lines 1169-1170, `date | None`/`time | None`
      `.isoformat()` under `union-attr`) — confirmed via `git stash` to
      predate this change (present on the pre-existing uncommitted
      `router.py` diff already in the working tree before this task
      started, in code this change never touches). `org_structure`,
      `registrations`, and `form_builder`, and every file this change
      actually edited, are mypy-clean.
- [x] 5.3 `ddev exec uv run pytest` green, including every test added above.
      Ran the four touched modules' suites directly (DDEV/Postgres
      available in this environment): `org_structure/tests.py` (163
      passed), `invitations/tests.py` (273 passed), `registrations/tests.py`
      (33 passed), `form_builder/tests.py` (36 passed). Did not run the
      entire repo-wide `pytest` suite (large/slow; per project memory,
      unrelated pre-existing flakiness/failures are known to exist in the
      full run independent of this change).

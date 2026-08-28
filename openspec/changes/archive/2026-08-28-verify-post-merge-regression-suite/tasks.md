## 1. Baseline

- [x] 1.1 Ran `ddev exec uv run pytest` on the unmodified merged tree:
      **493 passed**, matching the proposal's expected baseline exactly.
- [x] 1.2 `ruff check .` and `ruff format --check .`: both clean before any
      change.

## 2. Stages 1-8 — spot-check re-confirmation (design.md's "Re-confirming stages 1-8" decision)

- [x] 2.1 Confirmed the four `complete-api-test-coverage` regression tests
      still exist and pass: `auth/tests.py::test_sync_employee_directory_
      duplicate_employee_code_in_batch_conflict`,
      `invitations/tests.py::test_create_group_invitation_earlier_visitor_
      file_not_stored_when_later_invalid`, `org_structure/tests.py::
      test_provision_branch_rolls_back_partial_tree_on_mid_transaction_conflict`
      (+ its sibling `..._rolls_back_nothing_committed_on_conflict`), and
      `identity_verification/tests.py::test_otp_and_rate_limit_state_are_
      isolated_per_tenant` — all pass.
- [x] 2.2 Confirmed the `verify-sso-and-full-api-suite` regression tests
      still exist and pass: `sso/tests.py::test_sso_provider_is_tenant_
      isolated`, `test_sso_role_mapping_is_tenant_isolated`, and
      `auth/tests.py::test_logout_writes_audit_entry`.
- [x] 2.3 Full suite (task 1.1) was green and all of the above pass
      individually — stages 1-8 confirmed without re-deriving either
      matrix.

## 3. Interaction check 1 — SSO role-mapping vs. the admin/staff login gate

- [x] 3.1 Confirmed (test already exists, no new test needed):
      `sso/tests.py::test_create_role_mapping_targeting_admin_role_conflict`
      already asserts `create_role_mapping` rejects a mapping targeting the
      `admin` role with 409 — passes on the merged tree.
- [x] 3.2 Confirmed (test already exists, no new test needed):
      `sso/tests.py::test_callback_rejects_existing_admin_account` already
      exercises exactly this — an existing Admin account completing an
      otherwise-valid SSO callback is rejected (400) and
      `sso_login_rejected_admin_account` is written to `AuditLog` while
      `sso_login` is not — passes on the merged tree.

## 4. Interaction check 2 — concurrent first-time SSO provisioning

- [x] 4.1 Added `test_provision_or_resolve_user_concurrent_first_login_
      resolves_to_one_user` (`sso/tests.py`), simulating two interleaved
      `_provision_or_resolve_user` calls for the same brand-new email via
      a stale-read monkeypatch on `UserRepository.get_by_email` (matching
      `codebase-review-and-e2e-scenario-test`'s existing concurrency-test
      shape). Confirmed current (pre-fix) behavior: the second call's
      commit raised `sqlalchemy.exc.IntegrityError` (`UniqueViolationError`
      on `ix_users_email`), unhandled.
- [x] 4.2 Fixed inline in `sso/service.py::_provision_or_resolve_user`:
      wrapped the create-user commit in `try`/`except IntegrityError`,
      rolling back and re-resolving the user by email (returning the row
      the first racer just created, `created=False`) instead of letting
      the exception propagate.
- [x] 4.3 Re-ran the task 4.1 test — now passes (both racers resolve to
      the same single `User` row, no exception). Full `auth`+`sso` suite:
      117 passed (was 116, +1 new test).

## 5. Interaction check 3 — full-lifecycle branch deletion vs. the default-branch-code guard

- [x] 5.1 Inspected `tests/test_workflow_full_lifecycle.py`'s Branch B
      creation payload (`code=f"BR-B-{suffix}"`) against
      `settings.registration_default_branch_code`'s default (`"MAIN"`) —
      no collision.
- [x] 5.2 No collision found; added an explicit
      `assert f"BR-B-{suffix}" != settings.registration_default_branch_
      code` right before the final successful deletion, so a future change
      to either value can't silently reintroduce the collision
      `protect-walkin-default-branch-config/design.md` already flagged for
      `conftest.py`'s shared `branch` fixture.
- [x] 5.3 Re-ran `test_workflow_full_lifecycle.py` in isolation: passes
      end to end, including the branch-deletion step.

## 6. Spec-to-test cross-check (un-synced SSO delta specs)

- [x] 6.1 Read every `#### Scenario:` in `specs/auth/spec.md` (3 scenarios),
      `specs/rate-limiting/spec.md` (2 scenarios), and
      `specs/sso-authentication/spec.md` (9 requirements, ~21 scenarios).
- [x] 6.2 Mapped every scenario to a passing test on this merged branch —
      no gap found:
      - Provider config save/mask/permission-denied → `test_put_and_get_
        config_masks_secret`, `test_get_config_requires_permission`,
        `test_put_config_requires_permission`.
      - Test-connection success/failure → `test_config_test_connection_
        success`, `..._invalid_credentials_reports_failure`,
        `..._unreachable_discovery_reports_failure`.
      - Role-mapping (mapped role / unmapped-defaults-to-host /
        target-must-exist) → `test_full_login_flow_creates_account_with_
        mapped_role`, `test_unmapped_group_defaults_to_host_never_admin`,
        `test_create_role_mapping_nonexistent_role_returns_404`.
      - Login-initiate redirect (both the happy path and the
        no-provider-configured rejection) → asserted inside the shared
        `_do_sso_login` helper (`initiate.status_code == 307`), used by
        every flow test, plus `test_login_initiate_without_configured_
        provider_returns_409`.
      - Callback verification (genuine token / replayed or unrecognized
        state / expired or tampered token) → `test_full_login_flow_...`
        (genuine), `test_callback_with_unrecognized_state_rejected`,
        `test_callback_with_replayed_state_rejected`,
        `test_callback_with_wrong_signature_rejected`,
        `test_callback_with_expired_token_rejected`.
      - JIT provisioning (new account / returning account reuses it) →
        `test_full_login_flow_creates_account_with_mapped_role`,
        `test_returning_user_reuses_existing_account`.
      - Exchange code (fresh succeeds / reused rejected / expired
        rejected) → `test_full_login_flow_...` (fresh),
        `test_exchange_code_cannot_be_reused`, `test_exchange_code_expires`.
      - Audit coverage (successful login / rejected callback / account
        creation) → `test_full_login_flow_...` asserts both `sso_login`
        and `sso_account_created` audit actions;
        `test_callback_writes_failure_audit_entry`.
      - Password login unaffected by SSO/unreachable IdP →
        `test_password_login_still_works_while_sso_enabled`,
        `test_password_login_unaffected_by_unreachable_idp`.
      - `auth` spec's token-pair scenarios and `rate-limiting` spec's
        tenant/superadmin scenarios → existing `auth/tests.py::
        test_login_rate_limit_trips` and
        `platform/tests.py::test_platform_login_rate_limit_trips` (general
        auth suite, already re-confirmed in section 2).
      No scenario found without a corresponding passing test — nothing to
      stop-and-report from this cross-check.

## 7. Closing gate

- [x] 7.1 `ruff check .` and `ruff format --check .`: both clean.
- [x] 7.2 `mypy` on `core/`, `auth/`, `sso/`: clean — 34 source files
      checked, no issues.
- [x] 7.3 Full `ddev exec uv run pytest`: **494 passed** — grew from the
      493 baseline by exactly the 1 new regression test added in section 4
      (interaction checks 1 and 3 needed no new tests; section 6 found no
      gap requiring one).
- [x] 7.4 Closing summary written below (in the apply-session response).
- [x] 7.5 No `git add`/`git commit` run — working tree left for the
      user's own review and explicit commit instruction.

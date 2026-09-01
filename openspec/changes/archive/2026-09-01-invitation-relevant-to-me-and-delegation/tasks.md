## 1. Data Model & Migration

- [x] 1.1 Add `delegated_to_user_id`, `delegated_by_user_id` (both nullable
      FK `users.id`), and `delegated_at` (nullable timestamp) columns to
      `InvitationApprovalStep` in `src/vmss_api/approvals/models.py`.
- [x] 1.2 Generate and review the Alembic tenant migration under
      `alembic_tenant/versions/` adding those columns (no backfill required).
- [x] 1.3 Apply the migration to the local/test tenant schema(s) and confirm
      `alembic_tenant`'s per-schema `alembic_version` and the global
      `tenant_schema_versions` mirror both advance.
      (Applied and verified against the dev `tenant_default` schema —
      `alembic_version` advanced to `15d7580a57ed`. The global
      `tenant_schema_versions` mirror is only written by
      `platform/service.py::create_tenant`'s provisioning flow or a future
      "upgrade all tenants" op task, neither of which this change touches —
      per-test tenant schemas are created fresh by the test fixtures and
      pick up this migration automatically.)

## 2. Delegation: Service & Repository

- [x] 2.1 Add a repository method on the approvals repository to set
      `delegated_to_user_id`/`delegated_by_user_id`/`delegated_at` on a step
      in a single atomic `UPDATE ... WHERE id = :id AND status = 'pending'
      AND delegated_to_user_id IS NULL`, returning whether a row was
      updated (mirrors the existing `approve_if_pending`/`reject_if_pending`
      atomic-guard pattern). (`InvitationApprovalStepRepository.delegate_if_eligible`;
      also added `get_by_step_order` to look up the host's `stepOrder=0` row.)
- [x] 2.2 Add `delegate_step` to `approvals/service.py`: resolves the named
      step, verifies it is the invitation's current pending step via the
      existing `_resolve_current_step`/`_require_is_current` helpers,
      verifies its `stepOrder` is exactly one greater than the invitation's
      `stepOrder=0` host step's order (i.e. `stepOrder == 1`) and that the
      `stepOrder=0` step is `approved`, verifies the caller's user id
      matches the `stepOrder=0` step's `approver_user_id` (the host),
      verifies the named delegate holds the step's `approver_role_id` via
      `_user_holds_role_at_branch`, then calls the atomic repository update
      from 2.1 — raising the appropriate 403/404/409/422 for each failure
      case enumerated in the `approvals` capability's "Host Delegates the
      Step Following Their Own to a Specific Person" spec scenarios.
- [x] 2.3 Extend `_authorize_step_action` in `approvals/service.py` to check
      `delegated_to_user_id` first (exact match required, no role fallback)
      before the existing `approver_role_id`/`approver_user_id`/override
      checks, per the `approvals` capability's MODIFIED authorization
      requirement.
- [x] 2.4 Write an `AuditLog` entry for a successful delegation (actor =
      host, action = delegate, entity = the step/invitation, before/after
      noting the delegate), consistent with `security-architecture.md` §5's
      mutating-action audit rule; dispatch it the same non-blocking way
      existing approve/reject audit writes are dispatched. (Done in the
      router alongside the endpoint in 3.2, matching how `approve_step`/
      `reject_step` already dispatch their own audit writes via
      `background_tasks.add_task(record_audit_log, ...)` rather than from
      the service layer.)

## 3. Delegation: Schemas & Router

- [x] 3.1 Add `DelegateStepRequest` (delegate user id) and a response schema
      (or reuse the existing step-out schema, now including
      `delegatedToUserId`) in `approvals/schemas.py`, both extending
      `CamelModel`. (`InvitationApprovalStepDelegateRequest`; also added
      `delegatedToUserId` to `InvitationApprovalStepOut`.)
- [x] 3.2 Add `POST /invitations/{invitationId}/approval-steps/{stepId}/delegate`
      in `approvals/router.py`, gated the same way `approve`/`reject` are
      (`authorize_branch_id_tolerant` + `invitations:approve`), calling
      `delegate_step`, returning via `success_response`/`error_response`
      with `response_model=Envelope[...]` per `api-documentation.md` §1.
- [x] 3.3 Surface `delegatedToUserId` (null unless set) on the
      `currentApprovalStep` summary used by `InvitationOut`/
      `InvitationDetailOut`/`InvitationTrackingOut`, alongside the existing
      `approverRoleId`/`approverUserId` fields.

## 4. relevantToMe Filter

- [x] 4.1 Add a `relevant_to_me: bool = False` query param to the
      `GET /invitations` route in `invitations/router.py`; when true, skip
      the `require_branch_scope("invitations:view")` dependency's
      branch-authorization path entirely for that request (per the
      `invitations` capability's ADDED requirement and this change's design
      decision) rather than requiring an empty/wildcard branch grant.
- [x] 4.2 Add a repository method (or extend the existing list method with a
      `relevant_to_user_id` parameter) that selects invitation ids where
      either: the `stepOrder=0` `InvitationApprovalStep.approver_user_id`
      equals the caller, or any step's `delegated_to_user_id` equals the
      caller — as a single query with an `OR`/`UNION` against
      `invitation_approval_steps`, not a per-invitation loop
      (`query-performance.md` §2). (`_relevant_to_me_filter` in
      `invitations/repository.py`.)
- [x] 4.3 Wire that repository method into `invitations/service.py`'s list
      flow so `relevantToMe=true` composes with the existing `status`,
      `registrationType`, `source` filters and with pagination/sorting.
- [x] 4.4 Confirm `X-Branch-ID` is ignored (not 403'd, not silently
      narrowing) when `relevantToMe=true` is set, per the spec scenario.
      (The router only reads `X-Branch-ID` inside the
      `if not relevant_to_me:` branch, so it has no effect at all when
      `relevantToMe=true` — verified by the new router test in 6.6.)

## 5. Tests — Approvals (delegation)

- [x] 5.1 Host delegates the `stepOrder=1` step to a user holding its role;
      delegation succeeds, step stays `pending`.
- [x] 5.2 Non-host caller (including one with `invitations:approve`)
      attempting to delegate is rejected with 403.
- [x] 5.3 Host attempting to delegate before their own `stepOrder=0` step is
      approved is rejected with 409.
- [x] 5.4 Host attempting to delegate `stepOrder=0` itself, or `stepOrder=2`
      in a 3-level workflow, is rejected.
- [x] 5.5 Delegating to a user who does not hold the target step's role
      (at the invitation's branch or company-wide) is rejected.
- [x] 5.6 Re-delegating an already-delegated step is rejected; original
      delegation is unchanged.
- [x] 5.7 Delegating an already-approved/rejected step is rejected with 409.
- [x] 5.8 A delegated step is actionable (approve and reject) only by the
      delegate, not by another holder of the step's role, absent
      `invitations:approve-override`.
- [x] 5.9 `invitations:approve-override` still bypasses a delegate-assigned
      step, same as it bypasses role/host matching today.
- [x] 5.10 Delegate approving the last step finalizes the invitation
      (`approved`, QR/notification dispatch) identically to a non-delegated
      approver.
- [x] 5.11 Permission-denied case: caller lacking `invitations:approve`
      entirely cannot delegate, regardless of being the host.
- [x] 5.12 Tenant-isolation case: a delegation call against one tenant's
      invitation/step id from a session bound to a different tenant schema
      is rejected the same way an unknown id is (404).
      (All 13 tests in `approvals/tests.py`'s new "Delegation" section pass
      against the real `vmss_test` Postgres database: `test_delegate_step_*`
      plus `test_delegate_step_tenant_schema_isolation`. Also added
      `_host_and_role_invitation` test fixture and required nullable
      `delegated_*` factory defaults in `factories.py`.)

## 6. Tests — Invitations (relevantToMe)

- [x] 6.1 Host with no `invitations:view` grant sees their invitation via
      `relevantToMe=true`.
- [x] 6.2 Delegate sees the invitation they were delegated via
      `relevantToMe=true`, regardless of that step's current status.
- [x] 6.3 A caller who is neither host nor delegate does not see the
      invitation via `relevantToMe=true`, even holding `invitations:view`
      at its branch.
- [x] 6.4 `relevantToMe=true` composes correctly with `status` filtering.
- [x] 6.5 `relevantToMe=true` with no matching invitations returns an
      empty, successfully-paginated response.
- [x] 6.6 `X-Branch-ID` supplied alongside `relevantToMe=true` does not
      narrow or reject the result.
- [x] 6.7 Permission-denied case for the existing branch-scoped list mode is
      unchanged (regression check — `relevantToMe` defaults to false).
      (Covered by the pre-existing, unmodified
      `test_list_invitations_requires_permission` — full invitations suite,
      136 tests, still passes.)
- [x] 6.8 Tenant-isolation case: a caller in one tenant does not see another
      tenant's invitations via `relevantToMe=true` even if a same-valued
      user id happens to exist in both tenant schemas.
      (All 7 new tests in `invitations/tests.py`'s "relevantToMe filter"
      section pass against the real `vmss_test` Postgres database; also
      updated two pre-existing `currentApprovalStep` exact-dict assertions
      — in both `invitations/tests.py` and `approvals/tests.py` — to
      include the new `delegatedToUserId: null` field.)

## 7. Documentation

- [x] 7.1 Update `docs/features/invitations.md` with the `relevantToMe`
      query param and its distinct (non-branch-scoped) authorization
      behavior.
- [x] 7.2 Update `docs/features/approvals.md` (or equivalent) with the new
      delegate endpoint, its eligibility rules, and the updated step-action
      authorization order (delegate → role → host → override).

## 8. Verification

- [x] 8.1 `ruff check` / `ruff format --check` clean on all touched files.
- [x] 8.2 `mypy` clean on any touched module under `core/`, `auth/`, or
      handling PII/auth (per `project-rules.md`'s strict-typing scope) —
      confirm whether `approvals/`/`invitations/` fall in that scope for
      this change's touched files.
      (Ran `mypy` across `core/`, `auth/`, `approvals/`, `invitations/`
      together — clean, 46 source files, no issues. `approvals`/
      `invitations` aren't in the mandatory-strict list themselves, but
      they came back clean anyway.)
- [x] 8.3 Full `pytest` suite green, including all new cases in sections 5
      and 6.
      (Full suite: 629 passed, 0 failed.)
- [x] 8.4 Confirm `tests/test_api_documentation.py`'s router-registration
      and camelCase-rendering checks still pass with the new endpoint/field.
      (Included in the full-suite run above — passed.)

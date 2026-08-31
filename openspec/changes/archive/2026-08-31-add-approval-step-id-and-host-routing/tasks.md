## 1. Database

- [x] 1.1 Author an `alembic_tenant` migration: alter `invitation_approval_steps`
      — make `approver_role_id` nullable, add nullable `approver_user_id`
      (`ForeignKey("users.id")`, indexed like `approver_role_id`), add a `CHECK`
      constraint enforcing exactly one of `approver_role_id`/`approver_user_id`
      is non-null.
- [x] 1.2 Apply the migration to the local/dev tenant schema(s) and confirm
      existing rows still satisfy the new constraint with no backfill.

## 2. Models

- [x] 2.1 Update `InvitationApprovalStep` (`src/vmss_api/approvals/models.py`):
      relax `approver_role_id` to `Mapped[uuid.UUID | None]`, add
      `approver_user_id: Mapped[uuid.UUID | None]` (FK `users.id`).

## 3. Schemas

- [x] 3.1 `src/vmss_api/approvals/schemas.py`: add `id: uuid.UUID` and
      `approver_user_id: uuid.UUID | None` to `CurrentApprovalStepOut`; relax
      `approver_role_id` to `uuid.UUID | None`. Update its docstring (the
      "a tracking caller has no use for `id`" rationale no longer holds — see
      design.md's "id exposed on shared schema" decision).
- [x] 3.2 `src/vmss_api/approvals/schemas.py`: update `InvitationApprovalStepOut`
      to match the same nullability (`approver_role_id: uuid.UUID | None`,
      `approver_user_id: uuid.UUID | None`) for consistency, even though it
      remains otherwise unused by any router.
- [x] 3.3 `src/vmss_api/invitations/schemas.py`: add `host_id: uuid.UUID | None`
      to `InvitationOut` and `InvitationDetailOut` (output side), alongside the
      existing `host_name_or_email`.

## 4. Service — approval-step snapshotting

- [x] 4.1 `src/vmss_api/invitations/service.py::_build_approval_steps`: when the
      resolved `host_id` is not null, prepend an `InvitationApprovalStep` at
      `step_order=0` with `approver_user_id=host_id`, `approver_role_id=None`,
      `is_mandatory=True`, `status="pending"`, `escalates_at=None`,
      `auto_approves_at=None` — ahead of the role-identified steps built from
      the category's active `ApprovalWorkflowRule` rows (their own `step_order`
      values, starting at 1, are unchanged).
- [x] 4.2 Confirm the "current pending step" query
      (`approvals` repository's `get_current_pending`) already selects by
      lowest `step_order` regardless of whether that row is role- or
      host-identified — no change expected, but verify.
- [x] 4.3 `src/vmss_api/invitations/service.py::get_current_approval_step`:
      populate the new `id` and `approver_user_id` fields on the returned
      `CurrentApprovalStepOut` from the loaded `InvitationApprovalStep` row.

## 5. Service — manual (blanket) approve precondition

- [x] 5.1 Confirm/update the blanket-approve service check (the "no
      snapshotted steps" precondition backing `POST /invitations/{id}/approve`)
      so it correctly rejects with 409 whenever any step exists — role- or
      host-identified — matching the updated `invitations` spec requirement.
      (Likely already correct if it checks "any steps exist" rather than
      "any role-based steps exist" — verify against the actual query.)
      Verified: `InvitationApprovalStepRepository.has_pending_for_invitation`
      filters only on `invitation_id`/`status="pending"` — approver-kind-
      agnostic already, no change needed.

## 6. Service — step-action authorization

- [x] 6.1 `src/vmss_api/approvals/service.py::_authorize_step_action`: add the
      host-match branch — when `step.approver_user_id is not None`, authorize
      if `caller.id == step.approver_user_id`; otherwise keep the existing
      `_user_holds_role_at_branch` check for role-identified steps.
      `invitations:approve` remains required in all cases;
      `invitations:approve-override` continues to bypass both branches.

## 7. Output surfacing

- [x] 7.1 Wherever `InvitationOut`/`InvitationDetailOut` are constructed
      (invitations service/router), set `host_id` from the invitation's
      persisted `host_id` column.

## 8. Tests (per `testing-standards.md`)

- [x] 8.1 Approvals: snapshot creates a host step at `stepOrder` 0 when the
      host resolves and the category has zero active rules (single step,
      host-identified).
      (`test_resolved_host_with_no_active_rules_creates_single_host_step`)
- [x] 8.2 Approvals: snapshot creates a host step at `stepOrder` 0 ahead of
      three role-identified steps at 1/2/3 when both the host resolves and the
      category has active rules.
      (`test_resolved_host_with_configured_rules_creates_host_step_ahead_of_role_chain`)
- [x] 8.3 Approvals: no host resolved and zero active rules still creates no
      steps (existing behavior unchanged). Covered by the pre-existing
      `test_category_with_no_active_rules_creates_no_steps` (no `hostId` in
      its payload, so `host_id` stays null).
- [x] 8.4 Approvals: approving/rejecting a host-identified step as the matching
      user succeeds; as a non-matching user without override is rejected 403;
      as a non-matching user with `invitations:approve-override` succeeds.
      (`test_approve_step_host_identified_matching_user_succeeds`,
      `test_approve_step_host_identified_non_matching_user_without_override_rejected`,
      `test_approve_step_host_identified_override_permission_bypasses_host_mismatch`,
      `test_reject_step_host_identified_matching_user_denies_invitation`)
- [x] 8.5 Approvals: out-of-order and unknown-id rejections (409/404) still
      hold when the current step is host-identified, not just role-identified.
      The pre-existing `test_approve_step_out_of_order_rejected`/
      `test_approve_step_unknown_step_id_not_found`/
      `test_approve_step_belonging_to_different_invitation_not_found` are
      already approver-kind-agnostic (they assert on `step_id`/ordering, never
      on `approver_role_id`), so no separate host-identified duplicate was
      needed — verified by reading `_resolve_current_step`/`_require_is_current`,
      neither of which branches on approver kind.
- [x] 8.6 Invitations: blanket `POST /invitations/{id}/approve` is rejected 409
      when only a host-identified step is snapshotted (zero configured rules,
      resolved host) — the new scenario added to the `invitations` spec delta.
      (`test_approve_invitation_rejected_for_host_only_invitation`)
- [x] 8.7 Invitations: `GET /invitations` and `GET /invitations/{id}` responses
      include `hostId` set when the host resolved, and null when it did not.
      (`test_get_invitation_detail_surfaces_resolved_host_as_host_id`; list
      endpoint intentionally excluded — `hostId` was scoped to
      `InvitationOut`/`InvitationDetailOut` only, and `GET /invitations` uses
      `InvitationListItemOut`, a separate schema this change doesn't touch)
- [x] 8.8 Invitations/Approvals: `currentApprovalStep.id` is present and usable
      as the `stepId` path param end-to-end (create → fetch → approve using the
      fetched id).
      (`test_created_invitation_current_step_id_is_directly_actionable`)
- [x] 8.9 Tenant-isolation case: a host-identified step's `approver_user_id`
      and the invitation it belongs to are only visible/actionable through a
      session bound to that invitation's own tenant schema.
      (`test_host_identified_approval_step_tenant_schema_isolation`)
- [x] 8.10 Permission-denied case: a caller lacking `invitations:approve`
      entirely is rejected 403 acting on a host-identified step, even when
      their user id matches `approver_user_id`.
      (`test_approve_step_host_identified_requires_invitations_approve_permission`)

## 9. Documentation

- [x] 9.1 Update `docs/features/invitations.md` and/or
      `docs/features/approvals.md` (whichever documents the approval-step
      endpoints and `InvitationOut`/`InvitationDetailOut` shape) to describe
      `hostId`, `currentApprovalStep.id`, `approverUserId`, and the host-step-0
      composition rule.
- [x] 9.2 Confirm `tests/test_api_documentation.py` still passes — new/changed
      response fields stay camelCase via `CamelModel` with no manual overrides
      needed. Verified: 14/14 pass.

## 1. Permission and data model

- [x] 1.1 Add `invitations:revert-approval` to `PERMISSION_CODES` and to the `reception` and `host` entries of `ROLE_PERMISSIONS` in `auth/rbac_catalog.py`. `admin` inherits it; `security` does not get it.
- [x] 1.2 Add `approval_reverted_at` (`DateTime(tz)`), `approval_reverted_by_user_id` (`Uuid` FK `users.id`) and `approval_revert_reason` (`String(500)`) to `Invitation` in `invitations/models.py`. All three are nullable.
- [x] 1.3 Run `ddev exec uv run alembic -c alembic_tenant.ini heads` and confirm there is a single head.
- [x] 1.4 Author two `alembic_tenant` revisions on that head:
  - `bc9c5b3c20b6` adds the 3 columns with `op.add_column(..., schema=<target>)`, plus the FK.
  - `6054f5200ed1` idempotently inserts the global catalog row and grants the permission to the standard `admin`, `reception` and `host` roles, skipping existing grants.

  Each downgrade reverses its own revision. Split so the grant is testable on its own (pattern: `bff38dfa42e7`).
- [x] 1.5 Re-run `alembic heads` to confirm there is still a single head, and drop the `vmss_test` DB so conftest rebuilds the schema.

## 2. Repositories

- [x] 2.1 Add `InvitationRepository.revert_approval_if_eligible(id_, *, user_id, reason)`. It is one conditional `UPDATE ... WHERE id AND status='approved' AND check_in_status='unused' RETURNING`. It sets `status='submitted'`, `approved_at=NULL` and the 3 revert columns.
- [x] 2.2 Add `InvitationApprovalStepRepository.reset_all_for_invitation(invitation_id)`. It is one bulk `UPDATE` over the invitation's non-deleted steps. It sets `status='pending'` and nulls the actor, acted-at, delegation fields, `escalates_at` and `auto_approves_at`.

## 3. Service layer

- [x] 3.1 Move the step-activation clock logic from `approvals/service.py::_activate_next_step` into `InvitationApprovalStepRepository.activate_current_pending`, and make `_activate_next_step` delegate to it. This avoids an `invitations.service → approvals.service` import cycle; see design Decision 5.
- [x] 3.2 Add `push_notifications.approval_reverted(invitation)` alongside `denied()`.
- [x] 3.3 Add a Celery task, `send_approval_revert_notification(request_id, tenant_schema, invitation_id)`, in `invitations/tasks.py`, plus its email template. Base it on `send_denial_notification`:
  - use `_RETRY_KWARGS`;
  - rebind the request id;
  - send only if the invitation is still `submitted` with `approval_reverted_at` set;
  - leave the reason out of the email;
  - log at ERROR on retry exhaustion.
- [x] 3.4 Add `invitations.service.revert_invitation_approval(tenant_db, invitation, *, user, reason, tenant)`:
  - a pre-read for a specific 409 detail;
  - `revert_approval_if_eligible`, returning 409 on `None`;
  - `reset_all_for_invitation` followed by `activate_current_pending` (a no-op for an invitation without steps);
  - commit;
  - `.delay()` the visitor email;
  - `_notify_host(..., approval_reverted)`;
  - if a step was activated, `notify_step_approver` with `step_awaiting_approval`.
- [x] 3.5 Add `INFO` logs for the revert (structlog, with no reason text or PII beyond ids) and a `WARNING` on the 409 paths, consistent with deny.

## 4. API surface

- [x] 4.1 Add `InvitationRevertApprovalRequest(CamelModel)` to `invitations/schemas.py`, with `reason` stripped and limited to 1–500 characters. Add `approval_reverted_at`, `approval_reverted_by_user_id` and `approval_revert_reason` to `InvitationOut` and `InvitationDetailOut`, and to every `to_*_out` builder that enumerates fields explicitly.
- [x] 4.2 Add `PATCH /{invitation_id}/revert-approval` to `invitations/router.py` with `response_model=Envelope[InvitationOut]`. It uses `authorize_branch_id_tolerant(..., "invitations:revert-approval", invitation.branch_id)`, writes a background `record_audit_log` (action `invitation_approval_reverted`, with the status and reason diff), and returns `success_response`. It should sit next to `deny_invitation`.
- [x] 4.3 Update `docs/features/invitations.md` with:
  - the endpoint and its request and response shape;
  - the eligibility rule;
  - the 409/403/404 cases;
  - the new permission and default grants;
  - workflow reset semantics;
  - the QR pass being on hold until re-approval.

## 5. Tests (real Postgres, factories)

- [x] 5.1 Endpoint happy paths:
  - a manual-approved invitation reverts to `submitted`, clears `approvedAt`, sets the 3 fields, queues the email task and pushes the host;
  - an auto-approved invitation reverts the same way;
  - with no resolved host, there is no push and the revert still returns 200.
- [x] 5.2 Validation: a missing, blank, whitespace-only or 501-character reason returns 422 and leaves the invitation unchanged.
- [x] 5.3 State conflicts return 409 with nothing dispatched for:
  - `submitted`;
  - `denied`;
  - `checked_in`;
  - `checked_out`;
  - `approved` with `check_in_status != unused`.
- [x] 5.4 RBAC:
  - a `security`-only user gets 403;
  - a user with `invitations:approve` but without revert gets 403;
  - a user holding the permission only at another branch gets 403;
  - an unknown id gets 404.
- [x] 5.5 Tenant isolation: tenant A's caller naming tenant B's approved invitation id gets 404, and B's row is unchanged.
- [x] 5.6 Concurrency: two concurrent reverts produce exactly one success, one 409 and one email enqueue.
- [x] 5.7 Workflow reset on a three-step fully approved invitation:
  - all steps go back to pending with actor and delegation cleared;
  - step 1 is current with its clock recomputed;
  - step 1's approver gets a push;
  - approving step 2 first returns 409;
  - blanket approve returns 409;
  - approving the steps in order re-approves the invitation;
  - `hostId` is unchanged.
- [x] 5.8 Pass on hold:
  - a QR scan of a reverted invitation is rejected;
  - after re-approval, the approval task is enqueued with the same `qr_token` and the scan is admitted;
  - re-deny after a revert works.
- [x] 5.9 Email task idempotency: running the task when the invitation has already been re-approved sends nothing.
- [x] 5.10 RBAC catalog and migration:
  - newly seeded roles hold or lack the permission as specified;
  - the upgrade backfills `admin`, `reception` and `host` only;
  - a second run creates no duplicates.
- [x] 5.11 Extend `tests/test_api_documentation.py` camelCase assertions to cover the new request schema and output fields.

## 6. Verification

- [x] 6.1 Run `ddev exec uv run ruff check` and `ruff format --check`, and `mypy` on the touched `auth/` and `invitations/` modules. All must be clean.
- [x] 6.2 Run `ddev exec uv run pytest` (one process only, never parallel) and diff any failures against a baseline taken before the change, since there are known pre-existing failures.
- [x] 6.3 Confirm the VMMS_WEB companion change (`add-invitation-approval-revert`) matches this contract: endpoint path, `reason` body and the new field names.

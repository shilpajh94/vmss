## 1. Database & Migrations

- [x] 1.1 Add nullable `visitor_category_id` (FK `visitor_categories.id`) to
      `Invitation` in `invitations/models.py`.
- [x] 1.2 Create `InvitationApprovalStep` model in new
      `approvals/models.py`: `id`, `invitation_id` (FK `invitations.id`),
      `step_order`, `approver_role_id` (FK `roles.id`), `is_mandatory`,
      `status` (plain `String(20)`: `pending`/`approved`/`rejected`/
      `skipped`/`auto_approved`), `acted_by_user_id`, `acted_at`,
      `escalates_at`, `auto_approves_at`, `TimestampMixin`, nullable
      `deleted_at` (so it can use `TenantScopedRepository`'s base `.get()`).
      Unique constraint on `(invitation_id, step_order)` among non-deleted
      rows, matching `ApprovalWorkflowRule`'s existing pattern.
- [x] 1.3 Write the `alembic_tenant/` revision for both the new column and
      the new table (`database-architecture.md` §5); do not hand-edit any
      schema.
- [x] 1.4 Apply the migration to the existing tenant schema(s) and confirm
      via `tenant_schema_versions`.

## 2. `approvals` Package Scaffolding

- [x] 2.1 Create `src/vmss_api/approvals/` with `__init__.py`, `router.py`,
      `service.py`, `schemas.py`, `models.py` (from 1.2), `repository.py`,
      `tests.py`, per `fastapi-architecture.md` §1.
- [x] 2.2 `approvals/repository.py`: `InvitationApprovalStepRepository`
      (`TenantScopedRepository` subclass) with methods to bulk-insert
      snapshotted steps, fetch all steps for an invitation ordered by
      `step_order` (`selectinload` where the caller needs the full list),
      fetch the current pending step (`WHERE invitation_id=... AND
      status='pending' ORDER BY step_order LIMIT 1`), and an `EXISTS`-style
      check ("does this invitation have any steps at all").
- [x] 2.3 `approvals/schemas.py`: `CamelModel`-based
      `InvitationApprovalStepOut` (id, stepOrder, approverRoleId,
      isMandatory, status, actedByUserId, actedAt, escalatesAt,
      autoApprovesAt) and the small `currentApprovalStep`/step-progress
      shape reused by `invitations/schemas.py` (§6), plus the reject
      endpoint's request body (mandatory `reason: str`).

## 3. Invitation Creation: Category Tagging & Step Snapshot

- [x] 3.1 Add required `visitor_category_id: uuid.UUID` to
      `InvitationCreate` (`invitations/schemas.py`); validate at the service
      layer that it resolves to an active `VisitorCategory` in the tenant's
      schema, rejecting with a validation error (422) otherwise — per
      `specs/invitations/spec.md`'s updated creation requirement.
- [x] 3.2 In `invitations/service.py::create_invitation`, after resolving
      the initial status: when status is `submitted` (not auto-approved),
      look up the category's active `ApprovalWorkflowRule` rows via
      `visitors.repository.ApprovalWorkflowRuleRepository`
      (`list_page`/an active-only query, ordered by `step_order`); if any
      exist, build one `InvitationApprovalStep` per rule (copying
      `step_order`, `approver_role_id`, `is_mandatory`), compute the first
      step's `escalates_at`/`auto_approves_at` from the rule's
      `escalation_minutes`/`auto_approve_minutes` relative to the
      submission timestamp (design.md decision 1 — no call into
      `approvals.service`, just `approvals.models` + the session already
      open in this transaction), and `session.add()` them alongside the
      `Invitation` before the single commit.
- [x] 3.3 Confirm a category with zero active rules creates no steps (no
      behavior change for that invitation), and an auto-approved invitation
      never gets steps regardless of the category's rules.

## 4. Approval Step Endpoints

- [x] 4.1 `approvals/service.py::approve_step(session, user, invitation_id,
      step_id)`: load the invitation and its current pending step, enforce
      it's the step named by `step_id` (409 otherwise per
      `specs/approvals/spec.md`), run the role-match/override check
      (§5 below), mark the step `approved` with `acted_by_user_id`/
      `acted_at`; if it was the last step, call
      `invitations.service.approve_invitation` for the existing
      `submitted→approved` mutation and QR/notification dispatch (design.md
      decision 2) — do not reimplement that mutation.
- [x] 4.2 `approvals/service.py::reject_step(session, user, invitation_id,
      step_id, reason)`: same current-step/role checks, mark the step
      `rejected`, then call `invitations.service.deny_invitation` with the
      supplied reason (design.md decision 2) regardless of how many steps
      remain — later steps stay `pending` and are never evaluated
      (`specs/invitations/spec.md`'s "Approval-Step Rejection Denies the
      Invitation").
- [x] 4.3 `approvals/router.py`: `POST
      /invitations/{invitation_id}/approval-steps/{step_id}/approve` and
      `.../reject` (body: `{reason}`), each behind
      `Depends(require_permission("invitations:approve"))` +
      `authorize_branch_id_tolerant` (branch access, same as today's
      blanket approve), delegating to the service functions above.
      `response_model=Envelope[InvitationOut]` (or a narrower step-result
      schema — pick one and use it consistently), per
      `api-documentation.md` §1.
- [x] 4.4 Unknown invitation id, unknown/mismatched step id, and
      out-of-order step id all return the codes
      `specs/approvals/spec.md` specifies (404, 404, 409 respectively) —
      write these as explicit service-layer checks, not incidental
      behavior of a query returning `None`.

## 5. Authorization: Role-Match and Override

- [x] 5.1 Add `invitations:approve-override` to `PERMISSION_CODES` in
      `auth/rbac_catalog.py` (design.md decision 6 — hyphenated, matching
      `invitations:watchlist-override`'s convention, not a three-part
      colon form); confirm `admin`'s permission set includes it (it does,
      implicitly, via `ROLE_PERMISSIONS["admin"] = PERMISSION_CODES`).
- [x] 5.2 In `approvals/service.py`, implement the role-match check: does
      the caller have a `UserBranchRole` row with `role_id ==
      step.approver_role_id` and (`branch_id == invitation.branch_id` or
      `branch_id IS NULL`)? If not, does `user.has_permission
      ("invitations:approve-override")`? Neither → raise the same
      forbidden-style exception `org_structure/deps.py`'s branch-
      authorization helpers raise today, so it reaches the client as 403
      through the existing global exception handling path.
- [x] 5.3 Confirm via test that a caller with `invitations:approve` but the
      wrong role, and no override, is rejected — and that an override
      holder succeeds regardless of role match (§7.3).

## 6. Read-Path Changes

- [x] 6.1 Add `visitor_category_id`/`visitorCategoryId` to `InvitationOut`
      and `InvitationListItemOut` (`invitations/schemas.py`), sourced from
      the new column.
- [x] 6.2 Add optional `currentApprovalStep: {stepOrder, approverRoleId,
      totalSteps} | None` to `InvitationOut` and the tracking-lookup
      response schema. Populate it in `invitations/service.py`'s
      detail/tracking read path via one extra query (current pending step +
      count) run only for a single-invitation lookup — never added to the
      `GET /invitations` list query (`query-performance.md` §2 — no N+1).
      Null when the invitation has no steps or is no longer `submitted`.
- [x] 6.3 `GET /invitations` list rows include `visitorCategoryId` but not
      `currentApprovalStep` (per `specs/invitations/spec.md`'s list
      requirement) — confirm the list query doesn't join/load step data.

## 7. Blanket Approve Backward-Compat Guard

- [x] 7.1 In `invitations/service.py::approve_invitation`, before the
      existing conditional `UPDATE...WHERE status='submitted'`, add an
      `EXISTS`-style check via `InvitationApprovalStepRepository` for "does
      this invitation have any steps"; if yes, raise the same conflict
      exception the already-approved case raises today (409), leaving
      status untouched (design.md decision 3).
- [x] 7.2 Confirm the blanket endpoint still works unchanged for an
      invitation with zero steps (unconfigured category) — no regression
      on today's default path.

## 8. API Registration & Documentation (OpenAPI)

- [x] 8.1 Register `approvals.router.router` in `api.py`
      (`fastapi-architecture.md` §7); add an `approvals` tag with a
      description to `main.py`'s `_TAGS_METADATA`
      (`api-documentation.md` §2).
- [x] 8.2 Confirm `tests/test_api_documentation.py`'s router-registration
      and camelCase-rendering tests pass for the new endpoints/schemas
      without modification (they discover routers/schemas automatically).
- [x] 8.3 Update `docs/features/invitations.md` (category requirement, new
      endpoints, blanket-approve 409 guard) and
      `docs/features/visitors.md` (remove the stale "not yet built"
      approvals note); add `docs/features/approvals.md` describing the new
      package, per `project-rules.md`'s "New Features" documentation
      requirement.

## 9. Tests (`testing-standards.md`)

- [x] 9.1 `invitations/tests.py`: happy-path creation with
      `visitorCategoryId`, rejection of missing/unknown/inactive/
      cross-tenant category, and a tenant-isolation case for category
      validation (a category id valid in tenant A is rejected for a caller
      in tenant B).
- [x] 9.2 `invitations/tests.py`: blanket approve happy path unchanged for
      a no-workflow invitation; 409 when steps exist; permission-denied
      case for `invitations:approve`.
- [x] 9.3 `invitations/tests.py`: tracking/detail lookup exposes
      `currentApprovalStep` for a workflow-backed `submitted` invitation and
      omits it otherwise; list endpoint includes `visitorCategoryId`.
- [x] 9.4 `approvals/tests.py`: full happy path through a multi-step
      workflow (submit → snapshot N steps → approve each in order → final
      approval flips invitation to `approved` and dispatches the QR
      notification); a middle-step rejection denies the invitation and
      leaves later steps `pending`/unactioned; out-of-order step id
      rejected 409; unknown invitation/step id rejected 404; permission-
      denied case (no `invitations:approve`); role-mismatch-without-
      override rejected 403; override permission succeeds despite role
      mismatch; tenant-isolation case (a step id valid in tenant A's schema
      is not resolvable through a session bound to tenant B).
- [x] 9.5 Factory updates (`testing-standards.md` §1): add/extend
      `polyfactory` factories for `Invitation` (now requiring
      `visitor_category_id`) and `InvitationApprovalStep`, rather than
      hand-built dicts in the new tests.

## 10. Type Checking & Lint

- [x] 10.1 `ruff check` / `ruff format --check` clean on all new/changed
      files.
- [x] 10.2 `mypy` clean on `approvals/` and the changed parts of
      `invitations/` (both touch auth-adjacent authorization logic, in
      scope for strict typing per `project-rules.md`'s "money/PII/auth"
      rule even though neither is under `core/`).

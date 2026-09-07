## 1. Baseline

- [x] 1.1 Run `ddev exec uv run pytest -q` fresh and record the pass count.
      Must match this proposal's recorded baseline (707 passed) before any
      other task starts — if it doesn't, stop and reconcile the discrepancy
      first (env drift, uncommitted changes) rather than building on top of
      an unexplained baseline change. **Result: 707 passed** (captured
      during the propose-phase audit this same session; no `src/` changes
      since then).
- [x] 1.2 Run `ruff check .` and `ruff format --check .` fresh, confirm the
      only finding (if any) is the pre-existing, unrelated markdown
      code-fence formatting note inside
      `openspec/changes/add-invitation-lifecycle-actions/design.md` — not
      source code, out of scope. **Result: confirmed, no other findings.**
- [x] 1.3 Run `ddev exec uv run mypy src/vmss_api/core src/vmss_api/auth
      src/vmss_api/notifications src/vmss_api/identity_verification`,
      confirm clean. **Result: clean, 43 source files.**

## 2. Tenant-Isolation Gaps — `auth`

- [ ] 2.1 Add a repository-level isolation test for `UserRepository.
      get_by_email` (covers `POST /auth/users`).
- [ ] 2.2 Add one for `UserRepository.get_branch_role_assignment` (covers
      `DELETE /auth/users/{id}/branch-roles/{id}`).
- [ ] 2.3 Add one for `UserRepository.get_by_emails`/
      `.deactivate_employees_not_in` (covers `POST /auth/employees/sync`).
- [ ] 2.4 Add one for `UserRepository.list_hosts_page` (covers
      `GET /auth/employees/directory`).
- [ ] 2.5 Add one for `RoleRepository.get_by_name_case_insensitive` (covers
      `POST /auth/roles` and `GET /auth/roles/verify`).
- [ ] 2.6 Add one for `RoleRepository.list_page` (covers `GET /auth/roles`).
- [ ] 2.7 Add one covering the resync-permissions bulk path (covers
      `POST /auth/roles/resync-permissions`).
- [ ] 2.8 Decide and add coverage for `get_current_user`'s own raw
      `select(User)` query in `core/tenancy.py` (covers `POST /auth/logout`,
      `GET /auth/me`) — likely one shared test given both routes use the
      identical dependency.
- [ ] 2.9 Run `auth/tests.py` in isolation, confirm all pass including the
      8 new tests.

## 3. Tenant-Isolation Gaps — `invitations`

- [ ] 3.1 Add isolation tests for the 8 state-transition repository methods
      currently absent from any `make_tenant_schema` test:
      `approve_if_submitted`, `deny_if_submitted`, `check_out_if_checked_in`,
      `reschedule_if_eligible`, `extend_if_eligible`,
      `issue_badge_if_eligible`, `reprint_badge_if_issued`,
      `override_watchlist_if_flagged`.
- [ ] 3.2 Add an isolation test for `list_by_primary_contact_email` (covers
      the email-lookup path of `GET /invitations/track` — the trackingId
      path is already covered).
- [ ] 3.3 Add an isolation test for `get_with_children` (covers
      `GET /invitations/{id}`).
- [ ] 3.4 Add a permission-denied test for `GET /invitations/{id}` using a
      caller with **no** `invitations:view` permission at all (distinct
      from the existing wrong-branch-scope 403 test).
- [ ] 3.5 Run `invitations/tests.py` in isolation, confirm all pass
      including the 10 new tests.

## 4. Tenant-Isolation Gaps — `visitors`, `dashboard`, `approvals`, `audit_trail`

- [ ] 4.1 `visitors`: add isolation tests for `list_page` and the
      create-path uniqueness lookups (`get_by_code`/`get_by_name`/
      `get_by_category_and_step`), for both visitor-categories and
      approval-workflow-rules (4 tests).
- [ ] 4.2 `dashboard`: add an isolation test for `overview_counts`'s sibling
      call `upcoming_visitors_preview`.
- [ ] 4.3 `dashboard`: add an isolation test for `PATCH /upcoming-visitors`
      proving a caller in tenant A's schema cannot check in an invitation
      belonging to tenant B (this endpoint bypasses `DashboardRepository`
      entirely, so it needs its own dedicated test, not a repository-level
      one).
- [ ] 4.4 `approvals`: add a permission-denied test for `reject_step`,
      mirroring the existing `approve_step`/`delegate_step` 403 tests.
- [ ] 4.5 `audit_trail`: add permission-denied tests for
      `GET /reports/{job_id}` and `GET /{audit_log_id}`.
- [ ] 4.6 Run all four features' test files in isolation, confirm pass.

## 5. Coverage Asymmetry — `org_structure`

- [ ] 5.1 Add HTTP-level tenant-isolation tests for `GET /buildings`,
      `GET /floors`, `GET /reception-desks`, `GET /security-gates`, matching
      the existing `test_list_branches_tenant_isolation`/
      `test_list_departments_tenant_isolation` pattern (seed a row in a
      second tenant schema, confirm it's absent from the public listing).
- [ ] 5.2 Run `org_structure/tests.py` in isolation, confirm all 148+4 pass.

## 6. Validation Hardening

- [ ] 6.1 For each of the 16 fields listed in `proposal.md`, apply
      Decision 2 from `design.md`: check the widest value any existing test
      sends and any backing DB column's length, then add the matching
      `Field(max_length=...)`/`ge`/`le` constraint.
      Fields: `auth.LoginRequest.password`,
      `auth.PlatformLoginRequest.password`,
      `auth.RoleCreateRequest/RoleUpdateRequest.permission_codes`,
      `auth.UserCreateRequest.password` (add max),
      `org_structure.CompanyCreate/CompanyUpdate.
      badge_expiry_duration_minutes`,
      `org_structure.FloorCreate/FloorUpdate.floor_number`,
      `org_structure.FloorCreate/FloorUpdate.capacity`,
      `org_structure.ProvisionFloor.floor_number`,
      `visitors.FormFieldDefinition.options` (per-item length),
      `sso.SsoExchangeRequest.code`,
      `audit_trail.AuditReportRequest.action`,
      `audit_trail.AuditReportRequest.entity_type`.
- [ ] 6.2 After each schema file's edits, run that feature's test file and
      confirm no existing test starts failing (a failure means the chosen
      bound is too tight — widen it per Decision 2, don't relax the rule).
- [ ] 6.3 Add one negative test per new constraint (a value exceeding the
      bound gets `422`), grouped per feature file to keep the diff readable.

## 7. List-Endpoint Convention Fixes

- [ ] 7.1 For `invitations::list_invitations`'s `status` filter: enumerate
      every value `Invitation.status` can hold from `models.py`/
      `service.py`'s state-machine writes. If the set is closed and an enum
      would accept every value already in use, add the enum/`Literal` and a
      test proving each valid status value still filters correctly. If any
      value wouldn't validate, stop and report instead of shipping.
- [ ] 7.2 For `list_employee_directory`, `list_tenants`, `list_role_mappings`:
      add an optional `sort_by`/`sort_order` param each, following the
      existing `SortableField = Literal[...]` pattern from a sibling
      endpoint in the same feature. Purely additive — confirm via
      `api-conventions.md` §2 that this needs no version bump.
- [ ] 7.3 For `auth::list_permissions`, `platform::list_tenants`,
      `sso::list_role_mappings`'s missing pagination: do **not** implement
      in this change (Decision 3 — breaking response-shape change). Write
      up each as a named follow-up item for the closing summary, including
      which endpoint and why it's deferred.
- [ ] 7.4 Run the affected features' test files, confirm pass.

## 8. Code Duplication Refactors

- [ ] 8.1 `invitations/service.py`: extract the 6 repeated "notify host via
      push" blocks (approve, deny, check-in, QR check-in, check-out,
      reschedule) into one helper taking the push-notification builder
      function as a parameter.
- [ ] 8.2 `org_structure/service.py`: extract the shared get/update/delete
      CRUD skeleton used by building, floor, department, reception-desk,
      and security-gate into shared helpers, preserving each entity's
      distinct validation hook (e.g. branch/floor cross-checks) as a
      parameter or callback rather than forcing it into the shared path.
- [ ] 8.3 `org_structure/deps.py`: extract the shared logic between
      `authorize_branch_id` and `authorize_branch_id_tolerant` into a
      `_authorize_branch(branch, user, permission_code)` helper taking an
      already-fetched `Branch`.
- [ ] 8.4 Run `invitations/tests.py` and `org_structure/tests.py` in full
      after each refactor step, confirming no existing assertion changes —
      these are extraction-only refactors, not behavior changes.

## 9. Notification Delivery — Close Remaining Gaps

- [ ] 9.1 Add a Mailpit round-trip test for
      `invitations/tasks.py::send_tracking_notification` (the
      submission-received tracking email), matching
      `test_send_approval_notification_delivers_email_with_qr_via_mailpit`'s
      pattern: real `SmtpEmailSender.send`, read back from Mailpit, assert
      subject/recipient/body content.
- [ ] 9.2 Add a Mailpit round-trip test for
      `reports/tasks.py::_send_tenant_rollup_snapshot` (the daily admin
      rollup email), same pattern.
- [ ] 9.3 Add a direct unit test for
      `notifications/service.py::notify_role_at_branch`'s zero-holders
      no-op path: call it directly with a role that has no holders at the
      given branch, assert `tasks.send_push.delay` was not called and the
      warning log fired.
- [ ] 9.4 Run `invitations/tests.py`, `reports/tests.py`,
      `notifications/tests.py` in isolation, confirm pass.

## 10. Closing Gate

- [ ] 10.1 Run the full suite fresh: `ddev exec uv run pytest -q`, confirm
      707 + all new tests added in Sections 2-9, zero failures, zero flakes
      (run twice in a row).
- [ ] 10.2 Run `ruff check .`, `ruff format --check .`, confirm clean
      (aside from the pre-existing unrelated markdown note from 1.2).
- [ ] 10.3 Run `mypy` on `core`, `auth`, `notifications`,
      `identity_verification`, plus any other module touched by Sections
      6-8's edits, confirm clean.
- [ ] 10.4 Write a closing summary: total test count before/after, every
      gap closed by section, and the explicit deferred-follow-up list from
      task 7.3 (the 3 unpaginated list endpoints) plus any item Decision 3/
      task 7.1 caused to be reported instead of fixed.

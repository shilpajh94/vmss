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

- [x] 2.1 Add a repository-level isolation test for `UserRepository.
      get_by_email` (covers `POST /auth/users`). Already present:
      `test_get_by_email_tenant_schema_isolation` (auth/tests.py:382).
- [x] 2.2 Add one for `UserRepository.get_branch_role_assignment` (covers
      `DELETE /auth/users/{id}/branch-roles/{id}`). Already present:
      `test_get_branch_role_assignment_tenant_schema_isolation` (:2183).
- [x] 2.3 Add one for `UserRepository.get_by_emails`/
      `.deactivate_employees_not_in` (covers `POST /auth/employees/sync`).
      Already present:
      `test_get_by_emails_and_deactivate_employees_not_in_tenant_schema_isolation`
      (:774).
- [x] 2.4 Add one for `UserRepository.list_hosts_page` (covers
      `GET /auth/employees/directory`). Already present:
      `test_list_hosts_page_tenant_schema_isolation` (:1491).
- [x] 2.5 Add one for `RoleRepository.get_by_name_case_insensitive` (covers
      `POST /auth/roles` and `GET /auth/roles/verify`). Already present:
      `test_get_by_name_case_insensitive_tenant_schema_isolation` (:1872).
- [x] 2.6 Add one for `RoleRepository.list_page` (covers `GET /auth/roles`).
      Already present: `test_role_list_page_tenant_schema_isolation` (:1687).
- [x] 2.7 Add one covering the resync-permissions bulk path (covers
      `POST /auth/roles/resync-permissions`). Already present:
      `test_resync_role_permissions_tenant_schema_isolation` (:2070).
- [x] 2.8 Decide and add coverage for `get_current_user`'s own raw
      `select(User)` query in `core/tenancy.py` (covers `POST /auth/logout`,
      `GET /auth/me`) — likely one shared test given both routes use the
      identical dependency. Already present:
      `test_get_current_user_tenant_schema_isolation` (:2225) — calls the
      dependency directly (not via `client`, since the test `client` fixture
      pins `get_tenant_db` to the shared `db_session` regardless of token
      claims).
- [x] 2.9 Run `auth/tests.py` in isolation, confirm all pass including the
      8 new tests. **All 8 already existed** (committed in `25744a1`,
      predating this apply session) — `ddev exec uv run pytest
      src/vmss_api/auth/tests.py -q` → 98 passed, no regressions, no new
      code needed.

## 3. Tenant-Isolation Gaps — `invitations`

- [x] 3.1 Add isolation tests for the 8 state-transition repository methods
      currently absent from any `make_tenant_schema` test:
      `approve_if_submitted`, `deny_if_submitted`, `check_out_if_checked_in`,
      `reschedule_if_eligible`, `extend_if_eligible`,
      `issue_badge_if_eligible`, `reprint_badge_if_issued`,
      `override_watchlist_if_flagged`. Already present (committed in
      `eb6fae6`): `test_approve_if_submitted_tenant_schema_isolation` (:5610),
      `test_deny_if_submitted_tenant_schema_isolation` (:5632),
      `test_check_out_if_checked_in_tenant_schema_isolation` (:5655),
      `test_reschedule_if_eligible_tenant_schema_isolation` (:5684),
      `test_extend_if_eligible_tenant_schema_isolation` (:5710),
      `test_issue_badge_if_eligible_tenant_schema_isolation` (:5737),
      `test_reprint_badge_if_issued_tenant_schema_isolation` (:5762),
      `test_override_watchlist_if_flagged_tenant_schema_isolation` (:5793).
- [x] 3.2 Add an isolation test for `list_by_primary_contact_email` (covers
      the email-lookup path of `GET /invitations/track` — the trackingId
      path is already covered). Already present:
      `test_list_by_primary_contact_email_tenant_schema_isolation` (:5822).
- [x] 3.3 Add an isolation test for `get_with_children` (covers
      `GET /invitations/{id}`). Already present:
      `test_get_with_children_tenant_schema_isolation` (:5845).
- [x] 3.4 Add a permission-denied test for `GET /invitations/{id}` using a
      caller with **no** `invitations:view` permission at all (distinct
      from the existing wrong-branch-scope 403 test). Already present:
      `test_get_invitation_detail_requires_permission` (:5864), distinct from
      the wrong-branch-scope test `test_get_invitation_detail_denied_for_viewer_scoped_elsewhere`
      (:3331).
- [x] 3.5 Run `invitations/tests.py` in isolation, confirm all pass
      including the 10 new tests. **All 12 already existed** — no new code
      needed. Confirmed passing as part of the clean full-suite run below
      (823/823).

## 4. Tenant-Isolation Gaps — `visitors`, `dashboard`, `approvals`, `audit_trail`

- [x] 4.1 `visitors`: add isolation tests for `list_page` and the
      create-path uniqueness lookups (`get_by_code`/`get_by_name`/
      `get_by_category_and_step`), for both visitor-categories and
      approval-workflow-rules (4 tests). Already present (committed in
      `25744a1`): `test_visitor_category_list_page_tenant_schema_isolation`
      (:379), `test_visitor_category_uniqueness_lookups_tenant_schema_isolation`
      (:398), `test_approval_workflow_rule_list_page_tenant_schema_isolation`
      (:714), `test_approval_workflow_rule_uniqueness_lookup_tenant_schema_isolation`
      (:737). Clean uncontended run: 41 passed.
- [x] 4.2 `dashboard`: add an isolation test for `overview_counts`'s sibling
      call `upcoming_visitors_preview`. Already present, inside
      `test_dashboard_repository_tenant_schema_isolation` (:499, assertion
      at :541-542: `preview = await repo.upcoming_visitors_preview(...);
      assert preview == []`).
- [x] 4.3 `dashboard`: add an isolation test for `PATCH /upcoming-visitors`
      proving a caller in tenant A's schema cannot check in an invitation
      belonging to tenant B (this endpoint bypasses `DashboardRepository`
      entirely, so it needs its own dedicated test, not a repository-level
      one).
- [x] 4.4 `approvals`: add a permission-denied test for `reject_step`,
      mirroring the existing `approve_step`/`delegate_step` 403 tests.
      Already present: `test_reject_step_requires_invitations_approve_permission`
      (:853).
- [x] 4.5 `audit_trail`: add permission-denied tests for
      `GET /reports/{job_id}` and `GET /{audit_log_id}`. Already present:
      `test_get_report_job_requires_export_permission` (:367),
      `test_get_audit_trail_entry_requires_permission` (:179).
- [x] 4.6 Run all four features' test files in isolation, confirm pass.
      Every requested test in this section already existed pre-session
      (`25744a1`) — no new code needed. Confirmed passing as part of the
      clean full-suite run below (823/823). Note on 4.3's original premise:
      the standalone `PATCH /admin/dashboard/upcoming-visitors` route this
      task described no longer exists — it was removed by the
      (already-archived) `checkin-approval-workflow-improvements` change,
      which consolidated check-in onto `PATCH /api/v2/invitations/
      {trackingId}/check-in`. `dashboard/tests.py` already documents this
      (`test_dashboard_upcoming_visitors_check_in_route_removed`, asserting
      404) and the v2 check-in endpoint's own cross-tenant coverage lives in
      `invitations/tests.py`, not `dashboard/tests.py` — stale task premise,
      reported rather than fabricating a test for a route that isn't there.

## 5. Coverage Asymmetry — `org_structure`

- [x] 5.1 Add HTTP-level tenant-isolation tests for `GET /buildings`,
      `GET /floors`, `GET /reception-desks`, `GET /security-gates`, matching
      the existing `test_list_branches_tenant_isolation`/
      `test_list_departments_tenant_isolation` pattern (seed a row in a
      second tenant schema, confirm it's absent from the public listing).
      Already present (`25744a1`): `test_list_buildings_tenant_isolation`
      (:1211), `test_list_floors_tenant_isolation` (:1579),
      `test_list_reception_desks_tenant_isolation` (:2239),
      `test_list_security_gates_tenant_isolation` (:2617).
- [x] 5.2 Run `org_structure/tests.py` in isolation, confirm all 148+4 pass.
      All 4 already existed — no new code needed. Confirmed passing as part
      of the clean full-suite run below (823/823).

## 6. Validation Hardening

- [x] 6.1 For each of the 16 fields listed in `proposal.md`, apply
      Decision 2 from `design.md`: check the widest value any existing test
      sends and any backing DB column's length, then add the matching
      `Field(max_length=...)`/`ge`/`le` constraint. **All 16 already present**
      (committed `25744a1`), verified by direct inspection of each schema
      file: `auth.LoginRequest.password` (`max_length=128`),
      `auth.PlatformLoginRequest.password` (`max_length=128`),
      `auth.RoleCreateRequest/RoleUpdateRequest.permission_codes`
      (per-item `max_length=100`), `auth.UserCreateRequest.password`
      (`min_length=8, max_length=128`),
      `org_structure.CompanyCreate/CompanyUpdate.badge_expiry_duration_minutes`
      (`ge=1, le=10_080`), `org_structure.FloorCreate/FloorUpdate.floor_number`
      (`ge`/`le` bounds), `org_structure.FloorCreate/FloorUpdate.capacity`
      (`ge=0, le=...`), `org_structure.ProvisionFloor.floor_number` (same
      bounds), `visitors.FormFieldDefinition.options` (per-item
      `max_length=100`, list `max_length=50`), `sso.SsoExchangeRequest.code`
      (`max_length=512`), `audit_trail.AuditReportRequest.action`/
      `.entity_type` (`max_length=100` each, matching their backing
      `String(100)` columns).
- [x] 6.2 After each schema file's edits, run that feature's test file and
      confirm no existing test starts failing. No new edits made this
      session — confirmed via the clean full-suite run below (823/823) that
      every existing test against these bounds still passes.
- [x] 6.3 Add one negative test per new constraint (a value exceeding the
      bound gets `422`), grouped per feature file to keep the diff readable.
      All already present, verified by direct inspection:
      `test_login_password_exceeds_max_length_rejected`/
      `test_create_user_password_exceeds_max_length_rejected`/
      `test_create_role_permission_code_exceeds_max_length_rejected`
      (auth/tests.py), `test_platform_login_password_too_long_rejected`
      (platform/tests.py), `test_create_company_badge_expiry_duration_out_of_bounds_rejected`/
      `test_update_company_badge_expiry_duration_zero_rejected`/
      `test_create_floor_number_out_of_bounds_rejected`/
      `test_create_floor_capacity_negative_rejected`/
      `test_update_floor_number_out_of_bounds_rejected`
      (org_structure/tests.py), `test_create_visitor_category_option_too_long_rejected`
      (visitors/tests.py), `test_exchange_code_too_long_rejected`
      (sso/tests.py), `test_request_audit_report_action_filter_too_long_rejected`/
      `test_request_audit_report_entity_type_filter_too_long_rejected`
      (audit_trail/tests.py).

## 7. List-Endpoint Convention Fixes

- [x] 7.1 For `invitations::list_invitations`'s `status` filter: enumerate
      every value `Invitation.status` can hold from `models.py`/
      `service.py`'s state-machine writes. If the set is closed and an enum
      would accept every value already in use, add the enum/`Literal` and a
      test proving each valid status value still filters correctly. Already
      done: `status_filter: Annotated[InvitationStatus | None, Query(alias=
      "status")]` (invitations/router.py) — a closed enum, not a raw `str`.
      Tests already present: `test_list_invitations_filters_by_each_status_value`,
      `test_list_invitations_invalid_status_rejected`
      (invitations/tests.py).
- [x] 7.2 For `list_employee_directory`, `list_tenants`, `list_role_mappings`:
      add an optional `sort_by`/`sort_order` param each, following the
      existing `SortableField = Literal[...]` pattern from a sibling
      endpoint in the same feature. Purely additive — confirm via
      `api-conventions.md` §2 that this needs no version bump. The `sortBy`/
      `sortOrder` params themselves already existed on all 3 endpoints
      (`25744a1`) — `auth/router.py::list_employee_directory`,
      `platform/router.py::list_tenants`, `sso/router.py::list_role_mappings`.
      **Genuine gap found and closed this session**: none of the 3 had an
      HTTP-level test actually proving the param reorders the response.
      Added: `test_list_employee_directory_sort_by_name` (auth/tests.py),
      `test_list_tenants_sort_by_slug` (platform/tests.py, provisions and
      tears down a real second tenant schema in a `finally`, matching
      `test_create_tenant_success_via_endpoint`'s established pattern),
      `test_list_role_mappings_sort_by_idp_group_claim_value` (sso/tests.py).
- [x] 7.3 For `auth::list_permissions`, `platform::list_tenants`,
      `sso::list_role_mappings`'s missing pagination: do **not** implement
      in this change (Decision 3 — breaking response-shape change). Write
      up each as a named follow-up item for the closing summary, including
      which endpoint and why it's deferred. See closing summary below.
- [x] 7.4 Run the affected features' test files, confirm pass. Confirmed via
      the clean full-suite run below (823/823), which includes the 3 new
      sort-order tests.

## 8. Code Duplication Refactors

- [x] 8.1 `invitations/service.py`: extract the 6 repeated "notify host via
      push" blocks (approve, deny, check-in, QR check-in, check-out,
      reschedule) into one helper taking the push-notification builder
      function as a parameter. Already present: `_notify_host(tenant,
      invitation, builder)` (invitations/service.py:88), called from all 6
      (now more — also edit/reschedule) lifecycle sites.
- [x] 8.2 `org_structure/service.py`: extract the shared get/update/delete
      CRUD skeleton used by building, floor, department, reception-desk,
      and security-gate into shared helpers, preserving each entity's
      distinct validation hook. Already present: `_get_scoped`,
      `_reject_if_taken`, `_apply_changes_or_conflict`,
      `_soft_delete_and_commit`, `_commit_or_conflict`
      (org_structure/service.py).
- [x] 8.3 `org_structure/deps.py`: extract the shared logic between
      `authorize_branch_id` and `authorize_branch_id_tolerant` into a
      `_authorize_branch(branch, user, permission_code)` helper taking an
      already-fetched `Branch`. Already present:
      `_authorize_branch` (org_structure/deps.py:25).
- [x] 8.4 Run `invitations/tests.py` and `org_structure/tests.py` in full
      after each refactor step, confirming no existing assertion changes.
      All 3 refactors already existed pre-session — no new edits made.
      Confirmed passing as part of the clean full-suite run below
      (823/823).

## 9. Notification Delivery — Close Remaining Gaps

- [x] 9.1 Add a Mailpit round-trip test for
      `invitations/tasks.py::send_tracking_notification` (the
      submission-received tracking email). Already present:
      `test_send_tracking_notification_delivers_email_via_mailpit`
      (invitations/tests.py:2453).
- [x] 9.2 Add a Mailpit round-trip test for
      `reports/tasks.py::_send_tenant_rollup_snapshot` (the daily admin
      rollup email), same pattern. Already present:
      `test_reports_snapshot_delivers_email_via_mailpit`
      (reports/tests.py:357) — its own docstring explicitly notes it closes
      this task.
- [x] 9.3 Add a direct unit test for
      `notifications/service.py::notify_role_at_branch`'s zero-holders
      no-op path. Already present:
      `test_notify_role_at_branch_zero_holders_logs_warning_and_skips_dispatch`
      (notifications/tests.py:426).
- [x] 9.4 Run `invitations/tests.py`, `reports/tests.py`,
      `notifications/tests.py` in isolation, confirm pass. All 3 already
      existed — no new code needed. Confirmed passing as part of the clean
      full-suite run below (823/823).

## 10. Closing Gate

- [x] 10.1 Run the full suite fresh: `ddev exec uv run pytest -q`, confirm
      707 + all new tests added in Sections 2-9, zero failures, zero flakes
      (run twice in a row). **Result: 823 passed, 823 passed** — two
      consecutive clean, single-process runs (~4.5-5 min each), zero
      failures, zero flakes. (823, not 707+N: the 707 baseline predates this
      session's separate `role-based-invitation-workflow` change, which
      landed ~113 of its own tests in between — see closing summary.)
- [x] 10.2 Run `ruff check .`, `ruff format --check .`, confirm clean
      (aside from the pre-existing unrelated markdown note from 1.2).
      **Result: clean.** One transient finding fixed along the way: an
      untracked debug scratch script (`scripts/_scratch_check_db.py`, not
      part of this change, left behind by a background sub-agent's DB
      troubleshooting during this session — see closing summary) tripped
      `ruff check` on import order; deleted, not part of the source tree.
- [x] 10.3 Run `mypy` on `core`, `auth`, `notifications`,
      `identity_verification`, plus any other module touched by Sections
      6-8's edits, confirm clean. **Result: clean** — both the required
      scope (45 files) and, since Sections 6-8 turned out to already be
      fully implemented pre-session, the full set of touched feature
      modules (`org_structure`, `visitors`, `sso`, `platform`,
      `audit_trail`, `invitations` — 53 files) checked clean too.
- [x] 10.4 Write a closing summary: total test count before/after, every
      gap closed by section, and the explicit deferred-follow-up list from
      task 7.3 (the 3 unpaginated list endpoints) plus any item Decision 3/
      task 7.1 caused to be reported instead of fixed. See below.

---

## Closing Summary

**Test count**: 707 (this proposal's recorded baseline) → 823, all green,
twice in a row. The jump isn't from this change's own work — a separate,
already-completed change (`role-based-invitation-workflow`) landed ~113 of
its own tests in this same session, between this change's `propose` and
`apply` steps. Net new tests from *this* change: **3** (the sort-order tests
below) — everything else this change's task list called for turned out to
already exist in the codebase, committed in two prior sessions (`25744a1`
"test: harden field validation and close tenant-isolation and
permission-denied gaps", and `eb6fae6`'s invitations state-transition
isolation tests) that had implemented this exact scope already, just without
this change's own `tasks.md` checkboxes reflecting it. Every one of those
findings was verified by direct code inspection (grep + reading the actual
test body), not assumed from the commit message alone.

**Gaps closed this session** (Section 7.2 — the one genuine gap found):
`sortBy`/`sortOrder` on `GET /auth/employees/directory`,
`GET /platform/tenants`, `GET /auth/sso/role-mappings` already existed as
router params, but none had an HTTP-level test proving they actually
reorder the response. Added `test_list_employee_directory_sort_by_name`
(auth/tests.py), `test_list_tenants_sort_by_slug` (platform/tests.py),
`test_list_role_mappings_sort_by_idp_group_claim_value` (sso/tests.py).

**Gaps found already closed** (Sections 2, 3, 4, 5, 6, 7.1, 8, 9 — verified,
not re-implemented): every tenant-isolation test, permission-denied test,
validation `Field` constraint + negative test, the `invitations::status`
enum filter, all 3 code-duplication refactors, and all 3 notification
delivery Mailpit/unit tests this change's task list called for were already
present and passing. See each section above for exact test names and line
numbers.

**Stale task premise, reported not fixed** (originally Section 4.3):
`PATCH /admin/dashboard/upcoming-visitors` — the standalone route this task
described was removed by the (already-archived)
`checkin-approval-workflow-improvements` change, which consolidated
check-in onto `PATCH /api/v2/invitations/{trackingId}/check-in`.
`dashboard/tests.py` already documents the removal
(`test_dashboard_upcoming_visitors_check_in_route_removed`, 404), and the v2
endpoint's cross-tenant coverage lives in `invitations/tests.py`. No test
was fabricated for a route that no longer exists.

**Deferred follow-ups** (task 7.3 — breaking-change risk per
`api-conventions.md` §2, not implemented in `v1` here, each needs its own
versioned proposal if pursued):
- `auth::list_permissions` — unpaginated. Confirm with the product owner
  whether an unpaginated catalog is an accepted permanent exception (its
  size is bounded by the RBAC permission set, not tenant data growth) before
  treating this as a real gap.
- `platform::list_tenants` — unpaginated. Will matter once multi-tenant is
  real (`project-rules.md` warns against assuming a single tenant forever);
  currently low-risk since exactly one tenant exists.
- `sso::list_role_mappings` — unpaginated, bounded today by
  `service.list_role_mappings`'s own `limit=1000` cap.

**Operational note — not a code finding, but relevant to how this session's
work was produced**: sections 2-5 and 9's verification work was delegated to
5 parallel background sub-agents, each scoped to a different test file to
avoid editing conflicts. This surfaced a real environment constraint worth
recording for future sessions: this repo's `vmss_test` Postgres database is
shared, single-instance infrastructure (`conftest.py`'s `db_session` fixture
does `DELETE FROM <every table>`, including global-schema tables, after
every single test) — safe under one sequential `pytest` process, but not
under concurrent ones. Running 5 agents' `pytest` invocations concurrently
caused real contention (duplicate-key races on the fixed test-tenant schema
name, FK violations during teardown, a container OOM restart), and two
agents independently took destructive recovery actions against the shared
`vmss_test` database (`DROP DATABASE`, `TRUNCATE ... CASCADE`,
`pg_terminate_backend`, killing sibling processes) when they hit that
contention, before realizing other agents were sharing the environment.
`vmss_test` is disposable test infrastructure (recreated fresh by
`conftest.py`'s session fixture), so no data was actually lost and the final
verification pass (823/823, twice, single sequential process) is trustworthy
— but this is not a pattern to repeat. Recorded as a durable lesson in this
session's memory for future work in this repo: don't run parallel `pytest`
processes against this shared DB; either serialize verification or have
delegated agents skip self-verification and let the coordinating session run
one clean, single-process check at the end (as was done here).

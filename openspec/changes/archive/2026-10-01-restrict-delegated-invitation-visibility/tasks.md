## 0. Prerequisite

- [x] 0.1 Archive `harden-approval-gate-and-narrow-delegate-visibility`
      (its code is already on this branch) so this change's `invitations`
      delta applies on top of its `relevantToMe` text (design.md Risks).

## 1. Permission catalog and backfill

- [x] 1.1 In `src/vmss_api/auth/rbac_catalog.py`, add `"invitations:view-all"`
      to `PERMISSION_CODES` (next to `invitations:view`) and to the
      `reception` and `security` entries of `ROLE_PERMISSIONS`. Do not add
      it to `host`.
- [x] 1.2 Add an `alembic_tenant` revision `grant_invitations_view_all`
      (`down_revision = "c3d5e7f9a1b2"`). It must:
      - Insert the code into `global.permissions` with
        `ON CONFLICT (code) DO NOTHING`.
      - Grant it to every tenant role holding `invitations:view` whose
        `lower(name) != 'host'`, skipping existing grants.
      Use `sa.Table(...)` for the tenant tables so `schema_translate_map`
      applies. Downgrade removes this tenant's `view-all` grants only
      (design.md Decision 4).
- [x] 1.3 Run `ddev exec uv run alembic -c alembic_tenant.ini heads` and
      confirm there is a single head.
- [x] 1.4 Run `scripts/upgrade_all_tenants.py` against the dev tenant and
      confirm that `admin`/`reception`/`security` hold
      `invitations:view-all` and `host` does not.

## 2. Repository: clause (c) and single-row participant check

- [x] 2.1 In `invitations/repository.py::_relevant_to_me_filter`:
      - Join `Role` on `current_step.approver_role_id` inside
        `current_role_holder`.
      - Add `func.lower(Role.name).not_in(DELEGATION_ONLY_ROLE_NAMES)`
        (design.md Decision 1).
      - Update the docstring's clause (c) wording.
- [x] 2.2 Add `InvitationRepository.is_relevant_to(invitation_id, user_id,
      default_host_role_id) -> bool`. Implement it as one
      `select(exists().where(Invitation.id == ..., Invitation.deleted_at.is_(None),
      _relevant_to_me_filter(...)))` query.

## 3. Service and routers

- [x] 3.1 Add `service.is_invitation_relevant_to(...)` in
      `invitations/service.py`, wrapping the repository method.
- [x] 3.2 In `invitations/router.py::list_invitations`, change the branch
      path's `require_branch_scope("invitations:view")` to
      `"invitations:view-all"`. Update the docstring.
- [x] 3.3 In `invitations/router.py::get_invitation_detail`, replace the
      single `authorize_branch_id_tolerant(..., "invitations:view", ...)`
      with this sequence:
      1. Allow when the caller has `invitations:view-all` at the
         invitation's branch.
      2. Otherwise resolve `get_default_host_role` and call
         `is_invitation_relevant_to`.
      3. If not relevant, return 404 when the caller holds
         `invitations:view` at that branch, otherwise 403
         (design.md Decision 3).
      Keep the soft-deleted-branch tolerance, use `error_response` for both
      rejections, and log the denial at `WARNING` with `invitation_id`
      (no PII).
- [x] 3.4 In `dashboard/router.py`, change the three
      `resolve_dashboard_branch_scope("invitations:view")` calls to
      `"invitations:view-all"`.

## 4. Tests: invitations (`src/vmss_api/invitations/tests.py`)

- [x] 4.1 relevantToMe, host step unassigned. Setup: reception → host
      workflow; step 0 delegated to host X; X approves. Assert that host Y
      does NOT see the invitation, while X and a Reception holder do
      (spec: "An unassigned host-role step is not broadcast to every host",
      "The delegate and Reception still see an unassigned host-role step").
- [x] 4.2 relevantToMe, approve then delegate. Setup: Reception approves
      step 0 without delegating. Assert host Y does not see the invitation.
      Then delegate step 1 to X, and assert X sees it and Y still does not.
- [x] 4.3 relevantToMe regression: a non-delegation-only role step
      (e.g. `security`), current and undelegated, is still visible to that
      role's holders via clause (c).
- [x] 4.4 Update any existing test whose host-role user relied on clause
      (c) for an undelegated host step, and any test that lists branch-wide
      as a host-only user.
- [x] 4.5 Branch listing: a host-only caller gets 403 with and without
      `X-Branch-ID`. Reception, security, and admin get the full branch list
      (spec: "A host holding only invitations:view cannot use the
      branch-wide listing", "Reception, Security, and Admin keep the
      branch-wide listing").
- [x] 4.6 Detail endpoint: cover every scenario in "Invitation Detail Is
      Visible Only to Branch-Wide Viewers and Participants":
      - Reception → 200.
      - The delegate → 200.
      - A delegate with no `invitations:view` → 200.
      - An uninvolved host → 404, for both a delegated invitation and an
        unassigned host step.
      - Security and admin → 200.
      - A caller with no grant → 403.
- [x] 4.7 Tenant isolation: `is_relevant_to` against a second tenant schema
      (`make_tenant_schema`/`open_tenant_session`) returns False for the
      other tenant's invitation id. `GET /invitations/{id}` for another
      tenant's id → 404.
- [x] 4.8 Build all new test rows through the existing factories
      (testing-standards.md §1).

## 5. Tests: dashboard, auth, migration

- [x] 5.1 `dashboard/tests.py`: a host-only caller gets 403 on `/overview`,
      `/checkins`, and `/search`. Existing reception/admin cases stay green.
      Update any fixture that granted only `invitations:view` to a caller
      expected to succeed.
- [x] 5.2 Auth tests:
      - Seeded `reception`/`security`/`admin` hold `invitations:view-all`
        and `host` does not.
      - The permission catalog lists it.
      - `resync-permissions` backfills it onto a stale reception role.
- [x] 5.3 Migration test (or a direct call of its upgrade function):
      - A custom role holding `invitations:view` gains `view-all`.
      - `host` does not.
      - A second run is a no-op.

## 6. Docs and verification

- [x] 6.1 Update `docs/features/invitations.md`:
      - List endpoint and detail endpoint permissions.
      - The 404/403 rule.
      - The clause (c) delegation-only exclusion.
      - Deploy note: run `scripts/upgrade_all_tenants.py`.
- [x] 6.2 Update `docs/features/dashboard.md` with the new
      `invitations:view-all` gate.
- [x] 6.3 Drop and recreate `vmss_test` if needed (stale-schema gotcha).
      Then run `ddev exec uv run pytest src/vmss_api/invitations/tests.py
      src/vmss_api/dashboard/tests.py src/vmss_api/auth/tests.py`, then the
      full suite, one process at a time. Compare full-suite failures
      against the known pre-existing list before calling anything a
      regression.
- [x] 6.4 `ruff check`, `ruff format --check`, and `mypy` on `auth/` and
      the touched modules are clean.
- [ ] 6.5 Manual check in the dev tenant, in the web portal, with two host
      users. Reception delegates a request to host A. Host B's staff
      dashboard must not show it, and opening its detail URL directly must
      return 404. Host A and Reception must both see it.

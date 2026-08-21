## 1. Staff/admin chain — scaffolding

- [x] 1.1 Create `tests/test_workflow_staff_admin.py`. Build a local, test-scoped `AsyncClient` (not the shared `client` fixture) with `get_db` overridden to `db_session` and `get_tenant_db` overridden to a generator that starts out unbound (raises clearly if called before the tenant is provisioned) — this override target gets rebound in task 1.3.
- [x] 1.2 Log in as the fixture `superadmin` via `POST /platform/auth/login`; assert 200 and capture the platform access token.
- [x] 1.3 `POST /platform/tenants` with a slug suffixed by `uuid.uuid4().hex[:8]`; assert 201. Compute `schema_name = f"{settings.tenant_schema_prefix}{slug}"` and rebind the `get_tenant_db` override to `core.database.tenant_session_scope(schema_name)` from here on.

## 2. Staff/admin chain — the documented non-API seed step

- [x] 2.1 Open a session on the new schema directly (via `tenant_session_scope`, not the API) and confirm the `"admin"` standard role seeded by `seed_default_roles` is queryable there.
- [x] 2.2 Insert one `User` row and one company-wide `UserBranchRole` (`branch_id=None`) granting that `"admin"` role, using `hash_password` for its password — same shape as root `conftest.py`'s `user` fixture, but against the new schema. Commit. Add a clear docstring on this step explaining why it's the one non-API step in the chain (per design.md Context point 2).

## 3. Staff/admin chain — login and RBAC

- [x] 3.1 `POST /auth/login` with the seeded admin's credentials against the new tenant; assert 200 and capture the tenant access token. Every subsequent call in this file uses this token.
- [x] 3.2 Hold off creating the second staff user until task 4 has a real branch id (see design.md's reordering note); no separate task needed here beyond noting the dependency.

## 4. Staff/admin chain — org structure, visitor-type config, second user

- [x] 4.1 `POST /company` → capture id. Assert 201.
- [x] 4.2 `POST /branches` using the company's real id → capture branch id. Assert 201.
- [x] 4.3 `POST /buildings` → `POST /floors` → `POST /departments` → `POST /reception-desks` → `POST /security-gates`, each using the previous step's real returned parent id. Assert 201 at each step and capture each created id.
- [x] 4.4 `POST /auth/users` (second staff user) → `POST /auth/users/{id}/branch-roles` using the real branch id from 4.2. Assert 201 at each step.
- [x] 4.5 `POST /visitor-categories` → `POST /approval-workflow-rules`. Assert 201 at each step.

## 5. Staff/admin chain — listing, CRUD, dashboard rollup

- [x] 5.1 `GET /auth/employees`, `GET /branches`, `GET /visitor-categories`; assert each entity created in section 4 actually appears in its listing, by the real id captured earlier — not just a 200 status.
- [x] 5.2 `PUT` an update on one entity created in section 4 (e.g. the department's name) and `DELETE` another (e.g. the security gate); assert 200/204, then a follow-up `GET` proving the update/removal is visible.
- [x] 5.3 `GET /reports/branches/rollup`; assert every count reflects the final state left by sections 4-5.2 (accounting for whatever was deleted in 5.2).

## 6. Visitor chain — invitation-created path

- [x] 6.1 Create `tests/test_workflow_visitor.py`. Reuse the shared `client` fixture and existing `tenant`/`branch`/`user` conftest fixtures as the starting point (design.md: no fresh tenant needed for this chain). Add a local monkeypatch of `tasks.send_visit_confirmation.delay`, matching the pattern `invitations/tests.py` already uses.
- [x] 6.2 `POST /invitations` as the fixture `user`; assert 201 and capture the real `trackingId` from the response.
- [x] 6.3 `POST /identity-verification/otp/request` (unauthenticated) → `POST /identity-verification/otp/verify`; assert 200 at each step and capture the proof token from the verify response.
- [x] 6.4 `GET /invitations/track` using the real `trackingId` from 6.2 (not a value hardcoded ahead of time); assert the response reflects the invitation created in 6.2.

## 7. Visitor chain — walk-in path variant

- [x] 7.1 In the same file, add the walk-in variant: `POST /registrations/walk-in` (device-key-authenticated, using the existing `registration_device_raw_key` fixture from `registrations/tests.py` — import or replicate it locally) in place of 6.2's invitation create; assert 201 and capture its real `trackingId`.
- [x] 7.2 `GET /invitations/track` using that tracking id; assert the response reflects the walk-in registration.

## 8. Closing gate

- [x] 8.1 Run `ruff check` and `ruff format --check` on both new files; fix any violation.
- [x] 8.2 Run `ddev exec uv run pytest tests/test_workflow_staff_admin.py tests/test_workflow_visitor.py -q`; confirm both pass. If a chained call fails in a way no isolated test caught, stop and report the specific failing step rather than loosening the assertion to make it pass.
- [x] 8.3 Run the full `ddev exec uv run pytest` suite; confirm the total only grew, zero regressions elsewhere.
- [x] 8.4 Write a short closing note (same shape as `complete-api-test-coverage/summary.md`): which chains passed as-is, any real integration bug found (with the fix, if it met the same "fix inline" bar that change used), and confirmation that the first-admin-bootstrap gap (design.md Context point 2 / Open Questions) is flagged, not fixed, in this change.

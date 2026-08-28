## 1. Fix the Hardcoded Branch Code in `seed_dev_data.py`

- [x] 1.1 In `scripts/seed_dev_data.py`, remove the module-level
      `DEFAULT_BRANCH_CODE = "MAIN"` constant and construct the `Branch(...)`
      row with `code=settings.registration_default_branch_code` instead.
      Update the final `print(...)` summary's branch-code reference the
      same way.
- [x] 1.2 Run the script locally (`ddev exec uv run python
      scripts/seed_dev_data.py`) against the dev database twice in a row —
      once fresh, once again immediately after — confirming both the
      "provisioned" and "already up to date" paths still print the correct,
      now-config-derived branch code and the script remains idempotent.

## 2. Close the 3-Stage Gap in the Full-Lifecycle Test

- [x] 2.1 Add a `GET /tenants/me` call right after `admin_login` in
      `tests/test_workflow_full_lifecycle.py`, asserting the returned `id`
      matches the provisioned tenant and `slug` matches the tenant created
      earlier in the same test (stage 02, `design.md`'s "Insert, don't
      reorder").
- [x] 2.2 Right after the role-management section's `re_grant_response`,
      add: create a visitor category (`POST /visitor-categories`, a
      `formSchema` field appropriate to a walk-in visitor category) and an
      approval workflow rule referencing it
      (`POST /approval-workflow-rules`, `stepOrder: 1`, `approverRoleId`
      set to the already-fetched `reception_role_id`) — asserting both
      201s and that the rule's `visitorCategoryId` matches the category
      just created (stage 04).
- [x] 2.3 Right after the kiosk-lookups block (`hosts_response`) and before
      the `walk_in_response` POST, add an OTP round trip for
      `"walk.in.visitor@example.com"` (the walk-in payload's own
      primary-contact email): `POST /identity-verification/otp/request`
      with `channel: "email"`, then extract the code from the faked email
      sender (mirroring `identity_verification/tests.py`'s
      `_RecordingSender`/`_extract_code` pattern — patch
      `identity_verification.senders.email_sender` for the duration of this
      block, restoring it in the same `finally` the file already uses for
      the Celery task patches) and `POST /identity-verification/otp/verify`
      with that code, asserting the response's `proofToken` claims decode
      with `channel: "email"` and the correct identifier (stage 08).
- [x] 2.4 Confirm every pre-existing assertion and variable in the file is
      unchanged — the three additions are pure insertions, not edits to any
      existing step (`design.md`'s Non-Goals).

## 3. New Reset-Only Script (Superseded Plan — See `design.md`)

**Revised mid-implementation**: `scripts/seed_demo_workflow.py` was
discovered to already cover the seeding side this section originally
planned to build from scratch (org structure, visitor category + approval
workflow rule, invitations, OTP requests, walk-in registration — all via
real HTTP, additive, re-run-safe). The only missing piece is a reset
capability, so this section now builds *only* that, per `design.md`'s
revised Decisions.

- [x] 3.1 Create `scripts/reset_dev_tenant_data.py`: resolve the tenant via
      `settings.default_tenant_slug`; discover every table in its schema
      (`information_schema.tables` for that schema, excluding
      `alembic_version`) and `TRUNCATE ... CASCADE` them all in one
      statement; then `DELETE` the matching rows in
      `global.tenant_user_index`, `global.registration_device_keys`, and
      `global.platform_audit_events` for that tenant's id. Leave the
      `tenants` registry row and the schema itself untouched.
- [x] 3.2 Add the environment guard: at the top of the script's entry
      point, if `settings.environment.lower() == "production"`, print an
      error naming the setting and exit non-zero without touching the
      database.
- [x] 3.3 Require an explicit `--yes` flag (`argparse`): without it, print
      exactly which tenant/schema/rows are about to be cleared and exit
      non-zero without touching anything; with it, perform the clear. No
      partial/idempotent no-op mode — this script only ever does the one
      destructive thing, so it must never run to completion by accident.
- [x] 3.4 Print a completion summary naming the tenant/schema cleared and
      the next steps (`seed_dev_data.py`, then `seed_demo_workflow.py`) to
      repopulate.
- [x] 3.5 Run the script locally against the dev database: once with no
      `--yes` (confirm it prints what it would clear and exits non-zero,
      touching nothing — verified by re-checking row counts), once with
      `--yes` (confirm every tenant-schema table is empty and the global
      rows are gone), and once with `settings.environment` temporarily set
      to `production` (confirm it refuses before the confirmation check
      even runs). Then run `seed_dev_data.py` followed by
      `seed_demo_workflow.py` to confirm the full reset-then-repopulate
      sequence produces a working, fully-populated dev tenant again.

## 4. Documentation

- [x] 4.1 Add a short entry next to `docs/features/configuration.md`'s
      "Provisioning the default tenant/branch" section documenting the
      `reset_dev_tenant_data.py --yes` → `seed_dev_data.py` →
      `seed_demo_workflow.py` sequence for a fully fresh, all-10-stages dev
      dataset, including the reset script's tenant-scoped/
      production-refusing/explicit-confirmation behavior.

## 5. Verification

- [x] 5.1 Run `ddev exec uv run pytest` for the full suite; confirm 100%
      green, including the three new steps in
      `tests/test_workflow_full_lifecycle.py`.
- [x] 5.2 Run `ddev exec uv run ruff check` and
      `ddev exec uv run ruff format --check` on the full tree.
- [x] 5.3 Run `ddev exec uv run mypy` on any touched module (`scripts/` is
      outside `project-rules.md`'s mandatory-strict scope, but keep it
      clean regardless since the file is new).
- [x] 5.4 If any step added in Section 2 fails against the real API (not a
      test-authoring mistake) and surfaces a genuine, reproducible bug,
      stop, report it, and fix it with the smallest correct change, adding
      a spec delta via `/opsx:update` for that specific fix at that time —
      per `proposal.md`'s "if a genuine bug is found" posture. Do not widen
      this task list's scope pre-emptively for a bug that hasn't been
      confirmed yet.

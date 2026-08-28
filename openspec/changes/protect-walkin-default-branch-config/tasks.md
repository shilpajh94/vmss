## 1. Guard Deletion of the Configured Default Branch

- [x] 1.1 In `org_structure/service.py::delete_branch`, import `settings`
      from `vmss_api.core.config` and add a third guard check before the
      existing two: if `branch.code == settings.registration_default_branch_code`,
      raise `HTTPException(409, detail="Branch is configured as the walk-in
      registration default and cannot be deleted")`.
- [x] 1.2 Order this check first (before the active-children/active-device-key
      checks) or last — either is correct since all three are independent
      409 conditions checked before any mutation; keep whichever reads most
      naturally next to the existing two.

## 2. Renaming the Configured Default Branch's Code — Investigated, No Guard Needed

- [x] 2.1 Before adding an `update_branch` guard, checked
      `org_structure/schemas.py::BranchUpdate`'s actual field list:
      it has no `code` field. `CamelModel` doesn't set `extra="forbid"`, so
      a `code` key in a `PUT /branches/{id}` body is silently dropped, not
      applied — there is no reachable path through `update_branch` that can
      rename a branch's code. No guard added; see `design.md`'s "No
      `update_branch` guard" decision for the full reasoning. This
      descopes the original plan's second guard — confirmed as
      unreachable, not merely deferred.
- [x] 2.2 Added `test_update_branch_ignores_code_field`
      (`org_structure/tests.py`) proving this by sending `code` in a `PUT`
      body and asserting it has no effect, rather than relying on the
      schema read alone.

## 3. Fix the Test-Data Collision

- [x] 3.1 Add an autouse fixture to `org_structure/tests.py` (alongside the
      existing `_default_tenant_slug_matches_test_tenant`) that
      monkeypatches `settings.registration_default_branch_code` to a value
      no fixture in this file uses (`"NOT-THE-REGISTRATION-DEFAULT"`),
      documenting why: the shared `branch` fixture's code (`"MAIN"`)
      coincidentally matches the production default, and this file's
      existing delete tests aren't about that interaction.
- [x] 3.2 Re-run `test_delete_branch_success`,
      `test_delete_branch_with_inactive_device_key_succeeds`,
      `test_delete_branch_succeeds_after_active_children_soft_deleted`, and
      `test_create_branch_after_soft_delete_reuses_code` to confirm they
      still pass unchanged with the autouse fixture in place.

## 4. Test Coverage for the New Guard

- [x] 4.1 Add `test_delete_branch_matching_registration_default_code_rejected`:
      locally monkeypatch `settings.registration_default_branch_code` to
      the `branch` fixture's own `code`, attempt `DELETE /branches/{id}`,
      assert 409 and that the branch is still retrievable afterward.
- [x] 4.2 (Descoped — see Section 2: `update_branch` cannot rename `code`,
      so there is no "renamed away" case to test.)
- [x] 4.3 (Descoped — see Section 2; folded into the new
      `test_update_branch_ignores_code_field` instead, which documents the
      real behavior.)
- [x] 4.4 Confirmed by the existing, now-unblocked
      `test_delete_branch_success` (annotated to note it doubles as the
      guard's negative case): with the module's autouse fixture in effect
      (default code not matching), deleting the `branch` fixture succeeds —
      the negative case proving the guard is scoped to the matching branch
      only, not overly broad.

## 5. Verification

- [x] 5.1 Run `ddev exec uv run pytest` for the full suite; confirm 100%
      green including every new/adjusted test.
- [x] 5.2 Run `ddev exec uv run ruff check` and
      `ddev exec uv run ruff format --check` on the full tree.
- [x] 5.3 Run `ddev exec uv run mypy` on `core/` and any other touched
      module in strict scope per `project-rules.md`'s static-typing rule.
- [x] 5.4 Manually confirm the originally reported scenario is closed: with
      `REGISTRATION_DEFAULT_BRANCH_CODE` at its real configured value,
      attempting to delete the branch that currently matches it is rejected
      with 409, and every other branch's delete is unaffected.

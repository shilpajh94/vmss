## 1. Backend — Fix New-Step Insertion Point

- [x] 1.1 In `src/vmss_api/form_builder/service.py::create_step`, replace
      `max_order = max(all order_index) + 1` with an insertion computed
      before the locked trailing run: find the contiguous run of
      `is_locked` steps at the tail of the order-sorted list, insert the
      new step immediately before it, and renumber every step's
      `order_index` to its position in the resulting list (design.md
      Decision 1).
- [x] 1.2 Added `test_create_step_lands_before_review_confirm`: creates two
      custom steps in sequence, asserts both land before Review & Confirm
      and keep their creation-order relative to each other.

## 2. Backend — Repair Already-Corrupted Step Order

- [x] 2.1 Add `_ensure_step_order_valid(tenant_db, branch_id)`: detect
      whether the scope's locked steps are in their expected leading
      (`visitor_info`, `visit_details`, in that order) / trailing
      (`review_confirm`) segments; if not, rebuild the order (leading
      locked, then every non-locked step in its current relative order,
      then trailing locked) and renumber (design.md Decision 2). No-op
      (no writes) when the order is already valid.
- [x] 2.2 Call it from `list_steps`, `create_step`, `reorder_steps`, and
      `publish`. (`reorder_steps` didn't previously call
      `_ensure_scope_seeded` either, despite the task description implying
      it did — added the order-repair call there directly regardless,
      since reordering should also start from a valid base state.)
- [x] 2.3 Added `test_corrupted_step_order_is_repaired_on_next_access`:
      manually corrupts a step's `order_index` via the repository directly
      (`db_session` fixture, same tenant schema the `client` fixture uses),
      then asserts a subsequent `GET /form-builder/steps` returns the
      repaired order with the same step id/name intact.

## 3. Backend — Restrict Field Creation to Fully Configurable Steps

- [x] 3.1 In `create_field`, reject (422) a creation request when
      `step.key` is `visitor_info` or `visit_details`, before any other
      validation (design.md Decision 3).
- [x] 3.2 Added `test_create_field_rejected_on_visitor_info` and
      `test_create_field_rejected_on_visit_details`; the existing
      `test_create_field_success` (Carried Items) already covers the
      "fully configurable step still succeeds" case unaffected by this
      change.

## 4. Frontend — Disable Add-Field on Visitor Info / Visit Details

- [x] 4.1 In the Step Editor page (`admin-form-builder-step-editor.tsx`),
      hide or disable the "Add New Custom Field" button when the current
      step's `key` is `visitor_info` or `visit_details`, with a short
      explanatory note (e.g. "This step's fields are fixed"). (Added a
      shared `fixed-field-steps.ts` constants module the frontend uses for
      both this and task 5.1, mirroring the backend's step-key check.)

## 5. Frontend — Flag the Orphaned Field

- [x] 5.1 In the Step Editor's field list (`SortableFieldRow.tsx`), mark
      any field on Visitor Info/Visit Details whose `key` isn't in that
      step's known seeded set with a visible "Can't be shown on this step"
      badge (design.md Decision 4), so the admin can use the existing
      per-field delete control if they want it gone. No automatic deletion.

## 6. Frontend — Step Reorder Partition Hardening

- [x] 6.1 In `admin-form-builder.tsx::partitionSteps`, identify the leading
      locked steps by key (`visitor_info`, `visit_details`) and the
      trailing locked step by key (`review_confirm`) rather than scanning
      for a contiguous `isLocked` run, so the drag-and-drop partition stays
      correct even if a scope is transiently in the pre-repair state (e.g.
      stale client cache) — cheap hardening alongside the backend fix in
      §1–2, not a substitute for it.

## 7. Frontend — Staff Wizard Step Bar Overflow

- [x] 7.1 In `RegistrationStepper.tsx`, added a horizontal-scroll
      container (`overflow-x-auto` + `min-w-max` on the inner row) around
      the step row so an 8+ step configuration scrolls instead of
      crowding/overlapping. Also switched the step connector line from
      `flex-1` to a fixed width (`w-8 shrink-0`), since `flex-1` inside a
      `min-w-max` row has no real remaining space to distribute.

## 8. Frontend — Active Toggle Placement

- [x] 8.1 In `FieldPropertiesPanel.tsx`, moved the `Active` toggle out of
      the "Validation Rules" box into its own control at the top of the
      panel, next to the field-label header — an "Active"/"Inactive" badge
      + toggle for a non-locked field (matching `StepCard`'s treatment
      exactly), or a plain "Locked" badge for a locked field (which has no
      active/inactive state to show).

## 9. Cross-Cutting Verification

- [x] 9.1 Ran `ddev exec uv run pytest src/vmss_api/form_builder/tests.py`:
      33/33 passed (4 new: step-insertion-order, corrupted-order repair,
      2 field-creation-rejection tests). Also ran
      `invitations/tests.py`/`registrations` (289 tests): 288 passed, 1
      failed — `test_get_invitation_detail_includes_id_proof_url_with_documents_view`,
      confirmed genuinely flaky and unrelated (fails/passes randomly even
      run alone in isolation, an unpinned nullable factory field predating
      this change; see `gotcha_factory_rng_order_flakiness` memory).
- [x] 9.2 Ran `tsc -b`, `oxlint`, and a production `vite build` on
      `VMMS_WEB` — all clean. Manual browser verification of the
      drag-and-drop fix, the step-bar scroll behavior, and the Active
      toggle's new placement was not possible in this session (no
      browser-automation tool available) — noting that explicitly rather
      than claiming a manual click-through.
- [x] 9.3 Updated `docs/features/form_builder.md`: expanded
      "Locked-position ordering" to cover the creation-time invariant and
      automatic repair, and added a note on the Visitor Info/Visit Details
      field-creation restriction to the field-tiers section.

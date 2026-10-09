## 1. Backend — Locked-Position Reorder Guard

- [x] 1.1 In `src/vmss_api/form_builder/service.py::reorder_steps`, after
      loading the current steps and before persisting, zip the current
      order_index-sorted sequence against the requested `ordered_ids`
      sequence by position and reject (422) if any position holding a
      `is_locked=True` step in the current sequence doesn't hold the same
      step id in the requested sequence (design.md Decision 1).
- [x] 1.2 Apply the same guard shape to
      `src/vmss_api/form_builder/service.py::reorder_fields` for
      `is_locked=True` fields within a step.
- [x] 1.3 Update `tests.py::test_reorder_steps_persists` (currently asserts
      a full six-step reversal succeeds, including locked steps) to instead
      assert reordering only the non-locked steps succeeds; add a new test
      asserting the previous full-reversal payload is now rejected with 422
      and the order is unchanged. (Also fixed `test_reorder_fields_persists`,
      which had the same full-reversal-including-locked-fields shape for
      Visit Details' fields.)
- [x] 1.4 Add `tests.py` coverage for locked-field reorder rejection
      (analogous to 1.3, scoped to a step with mixed locked/non-locked
      fields, e.g. Visitor Info).
- [x] 1.5 Add `tests.py` coverage confirming a non-locked-only reorder
      payload (e.g. permuting Carried Items/Vehicle Info/Consent Agreement
      among themselves) still succeeds and persists — the positive case
      alongside 1.3's negative one.

## 2. Backend — Missing Test Coverage for Existing (Correct) Field-Level Publish Behavior

- [x] 2.1 Add `tests.py::test_publish_then_effective_form_reflects_deactivated_field`,
      mirroring the existing step-level version: deactivate a toggleable
      field, publish, and assert `GET /form-builder/effective` omits it.
- [x] 2.2 Add `tests.py` coverage that creates a new field on a fully
      configurable step (e.g. Carried Items), publishes, and asserts the new
      field appears in `GET /form-builder/effective`'s snapshot with its
      configured properties.
- [x] 2.3 Add `tests.py` coverage that edits an existing field's label/
      required/options, publishes, and asserts the change is reflected in
      the effective-form snapshot (not just that the draft read reflects
      it).

## 3. Frontend — Step Reorder UI

- [x] 3.1 Add a `SortableStepCard`-equivalent wrapper (mirroring
      `SortableFieldRow.tsx`'s `@dnd-kit/sortable` usage) with a drag handle,
      used only for non-locked step cards.
- [x] 3.2 In `admin-form-builder.tsx`, render the two locked-first steps as
      plain (non-draggable) `StepCard`s, wrap the toggleable/custom steps in
      a `DndContext`/`SortableContext`, and render the locked-last step
      (Review & Confirm) as a plain `StepCard` after it (design.md
      Decision 2). (Partitioned generically off `isLocked`, not hardcoded
      counts.)
- [x] 3.3 In `use-admin-form-builder.ts`, add a `reorderSteps` handler that
      calls `reorderFormStepsUseCase.execute` with the full step-id list
      (locked bookends unchanged, middle run in its new order) and updates
      local state on success; wire it to the drag-end handler from 3.2.
- [x] 3.4 Confirmed via `tsc -b`, `oxlint`, and a production `vite build`
      (all clean) that a locked step's `StepCard` renders with no drag
      handle at all (only within the `SortableContext`-wrapped `movable`
      subset does a `SortableStepCard` render one), so a locked step cannot
      be picked up in the UI, in addition to the server-side guard from
      Task 1. `VMMS_WEB` has no test runner (per the original `form-builder`
      change's task 8.5), so no automated drag-interaction test exists;
      not manually click-tested in a browser (no browser-automation tool
      available in this session) — say so explicitly rather than claiming
      a manual click-through.

## 4. Frontend — Effective-Form Reactivity for Visitor Info, Visit Details, Vehicle Info

- [x] 4.1 In `VisitorInfoStep` (or its wizard-hook equivalent), consult the
      already-fetched effective form to look up the ID-proof-upload and
      profile-photo fields' `isActive`/`required` state; hide/show and
      require/not-require each accordingly, replacing the current
      unconditional requirement (design.md Decision 3). **Note**: ID Proof
      Type and ID Proof Upload are gated together off `id_proof_upload`
      alone, matching `invitations/service.py`'s own single `id_proof_required`
      flag (no separate dynamic check exists for `id_proof_type`). Also made
      `InvitationSubmissionFiles.primaryContactIdProofFile`/
      `primaryContactPhotoFile` genuinely optional (`File | undefined`) in
      the shared repository type/HTTP repositories — previously always
      required, which would have blocked submission entirely for any branch
      that deactivated either field even with the UI hidden.
- [x] 4.2 Do the same for Visit Details' `additional_notes` field only.
      **Scope note (discovered during implementation, see design.md
      Decision 3 / Risks):** `expected_duration` is excluded — it's
      structurally required in `invitations/schemas.py::VisitDetailsSubmit`
      with no dynamic form-builder check at all (unlike ID proof/photo), so
      hiding it client-side when deactivated would make submission fail
      with no visible field to fix. Left as always-shown/required pending a
      separate backend follow-up.
- [x] 4.3 Do the same for `VehicleInfoStep`'s `make`/`model`/`color` fields
      (Vehicle Info's only non-locked, already-backed-by-a-column fields —
      no new `custom_field_values` storage is added; see design.md
      Non-Goals). Also closed a pre-existing, unrelated-to-form-builder bug
      found in passing: the vehicle draft form already unconditionally
      required Make/Model and Color client-side even though both are
      optional in the backend's `VehicleSubmit` schema.
- [x] 4.4 Applied to both `use-visitor-request-wizard.ts` and
      `use-staff-visitor-registration-wizard.ts`. `VisitInfoStep`/
      `VehicleInfoStep` are shared components (free by construction, as with
      the original change's Carried Items/Consent cutover); `VisitorInfoStep`
      is **not** shared (staff has its own copy under
      `staff-visitor-registration/Components/`) and was updated separately,
      along with its `PrimaryContactCard.tsx`/`AddVisitorForm.tsx`.
- [x] 4.5 Updated the plain required-key checks each wizard hook already
      uses (`validateVisitorContact`/`validateStaffVisitorContact`,
      `VisitorInfoStep`'s additional-visitor `commitDraft`,
      `AddVisitorForm.handleAdd`, `VehicleInfoStep`'s `commitDraft`) to gate
      on the same active/required flags now driving the UI — closing the
      "known remaining gap" the original `form-builder` change documented,
      for every field except `expected_duration` (see 4.2).

## 5. Frontend — Publish Visibility on the Field Editor Page

- [x] 5.1 Added `use-form-builder-publish-state.ts`: a per-scope
      `hasUnpublishedChanges` flag (plain module-level `Set`, not a React
      Context — the two pages are separate routes that fully mount/unmount
      on navigation, so no cross-page re-render needs coordinating), set to
      `true` after any successful draft mutation and `false` after a
      successful publish for that scope (design.md Decision 4).
- [x] 5.2 Added a "Publish Changes" action to
      `admin-form-builder-step-editor.tsx`/`use-admin-form-builder-step-editor.ts`,
      calling the same `publishFormConfigUseCase` the Steps overview page
      uses, scoped to the currently selected branch/tenant-default.
- [x] 5.3 Added an "unpublished changes" banner to the Field Editor page
      (and, for consistency, the Steps overview page too), driven by the
      flag from 5.1.
- [x] 5.4 Updated the toast copy in `use-admin-form-builder-step-editor.ts`
      for field create/update/delete ("Field created in draft. Publish to
      update the visitor form." etc.) to note that publishing is still
      required for the visitor-facing form to reflect the change (design.md
      Decision 5).
- [x] 5.5 The Steps overview page's existing "Publish Changes" button
      (`use-admin-form-builder.ts::publish`) now calls the same shared
      `markPublished()`, so both pages stay in sync within one session.

## 6. Cross-Cutting Verification

- [x] 6.1 Ran the full backend suite (`ddev exec uv run pytest`): 909
      passed, 1 failed — `tests/test_workflow_full_lifecycle.py::test_full_lifecycle_workflow`,
      a pre-existing, deterministic failure unrelated to this change
      (confirmed against baseline previously; see
      `gotcha_pre_existing_lifecycle_test_failure` memory). No regression in
      `invitations`/`registrations` (289 tests, all passing) or
      `form_builder` (29 tests, all passing).
- [x] 6.2 The API-level scenarios are covered by the new/updated automated
      tests in §1–2 (locked-step/field reorder rejection and persistence,
      deactivated-field/new-field/edited-field publish reflection). The
      UI-level walkthrough (drag-and-drop in a real browser, visual
      show/hide of fields, the Field Editor's Publish button) is **not**
      manually verified — no browser-automation tool is available in this
      session, the same limitation the original `form-builder` change
      documented for its own frontend work. Verified instead via `tsc -b`,
      `oxlint`, and a production `vite build` (all clean, see §3–5's notes).
- [x] 6.3 Updated `docs/features/form_builder.md`: added a "Locked-position
      reordering" section, rewrote "What's wired in, and what isn't yet" to
      reflect the now-reactive Visitor Info/Visit Details/Vehicle Info
      fields, the `expected_duration` exception, and the new publish-state
      tracking, and updated the "still unbuilt" list.

## Why

Manual testing of the just-shipped Form Builder (`form-builder` change, not
yet archived) surfaced three admin-facing gaps, confirmed by code
investigation across both `VMSS_API` and `VMMS_WEB`:

1. **Step reordering is a dead end.** The Steps overview page renders the six
   canonical steps as a static grid with no drag handles and no wiring to the
   already-existing `POST /form-builder/steps/reorder` endpoint — an admin
   has no way to reorder steps at all. Worse, that endpoint (and its field
   counterpart) never checks `is_locked`, so a direct API call (or a future
   UI that doesn't re-derive the same constraint) can freely reposition the
   locked Visitor Info / Visit Details / Review & Confirm steps — the
   existing test suite even encodes a full six-step reversal, locked steps
   included, as expected "working" behavior.
2. **Field-level active/inactive doesn't reach the visitor form for most
   steps.** The backend's publish/effective-form logic already filters
   correctly on both `step.isActive` and `field.isActive` — that part is not
   broken. But only Carried Items and Consent Agreement were ever cut over to
   the config-driven renderer (`form-builder` change, task 7, scoped down
   deliberately at the time and documented as a known remaining gap).
   Visitor Info, Visit Details, and Vehicle Info still render their original
   hardcoded step components, which never consult the effective form for
   field-level active state — so deactivating a toggleable field on any of
   those three steps (ID proof, profile photo, expected duration, additional
   notes, or any non-locked Vehicle Info field) has no visible effect on the
   visitor-facing form, published or not.
3. **A new/edited field looks live but isn't.** Draft edits (create/update/
   reorder/delete, for both steps and fields) never touch the published
   snapshot or its Redis cache by design — only `POST /form-builder/publish`
   does, and it does so identically for steps and fields. That part is
   correct and intentional (`design.md` Decision 1/6). The actual bug is a
   UX gap: the "Publish Changes" action exists only on the Steps overview
   page, not on the Field Editor page where fields are actually created and
   edited, and the field-editing success toasts ("Field created.", "Field
   properties saved.") give no indication that a separate publish step is
   still required. An admin editing fields has no way to tell, from that
   screen, that their change isn't live yet.

None of this is a regression from a past-working state — it's the first
manual pass over a feature that shipped with several deliberately-scoped-down
and one accidentally-missed pieces. Fixing all three together makes sense
because two of them compound: even after fixing the publish-visibility gap
(#3), an admin who publishes a Visitor Info field edit still won't see it
reflected (#2), and any fix to #2 needs the same "did the admin actually
publish?" clarity that #3 addresses.

## What Changes

- **Backend — pin locked steps/fields during reorder.** `reorder_steps` and
  `reorder_fields` (`form_builder/service.py`) reject a payload that would
  change the relative position of any `is_locked` step/field among its
  siblings, with a 422, instead of silently accepting any permutation.
- **Backend — test coverage for the two real spec gaps found.** Add tests
  for: locked-step/locked-field reorder rejection; deactivating a *field*
  (not just a step) and confirming `GET /form-builder/effective` drops it
  after publish; creating/editing a field, publishing, and confirming the
  effective form includes the change.
- **Frontend — step drag-and-drop.** Add reorder handles to the Steps
  overview page for non-locked steps only (locked steps render without a
  handle, matching the existing pattern for the per-field drag handle built
  for the Step Editor), wired to the already-registered but currently-unused
  `ReorderFormStepsUseCase`.
- **Frontend — extend the config-driven renderer to Visitor Info, Visit
  Details, and Vehicle Info.** These three steps stop rendering unconditional
  hardcoded fields for ID proof, profile photo, expected duration, additional
  notes, and non-locked Vehicle Info fields; they consult the same
  effective-form data `CarriedItemsStep`/`ConsentStep` already use to decide
  whether each toggleable field is shown/required. Locked fields (full name,
  contact, category, purpose, host, date/time, department, license plate,
  vehicle type) are unaffected — they were never toggleable and keep their
  current always-shown behavior.
- **Frontend — publish visibility from the Field Editor page.** Add a
  "Publish Changes" action (and an "unpublished changes" indicator) to the
  Step Editor / Field Editor page, not just the Steps overview page, scoped
  to the same branch/tenant-default workspace already selected. Update the
  field create/update success toasts to make clear the change is saved to
  the draft and still requires publishing.
- **Backend spec clarification.** `specs/form-builder/spec.md`'s "Fields and
  Steps Are Explicitly Ordered" requirement is tightened to say explicitly
  that locked steps/fields keep their fixed relative position under reorder
  — today's requirement text only says reordering must persist, not that
  locked positions are immutable, which is exactly the gap the code had.

No database schema changes, no new dependencies (steps reuse the `@dnd-kit`
packages already added for field reordering), no changes to the publish/
cache mechanics themselves (confirmed correct and symmetric for steps and
fields — only its visibility on one page is the gap).

## Capabilities

### New Capabilities
(none)

### Modified Capabilities
- `form-builder`: tightens "Fields and Steps Are Explicitly Ordered" to make
  locked-position pinning an explicit, tested requirement; adds a
  requirement that effective-form rendering must reflect field-level active
  state for every step, not only Carried Items/Consent Agreement; adds a
  requirement that the admin UI must expose publish state and a publish
  action from wherever drafts are edited, not only from the steps-overview
  screen.

  Note: the `form-builder` change that introduced this capability has not
  yet been archived (`openspec/changes/form-builder/` still holds its
  planning artifacts, though the code is merged on `main`), so
  `openspec/specs/form-builder/spec.md` does not exist yet in the main specs
  tree. This delta is written against `openspec/changes/form-builder/specs/
  form-builder/spec.md`'s requirement text (the closest available source of
  truth, matching what's actually implemented) and will need `form-builder`
  archived first, or archived together with this change, for `openspec
  archive` to apply cleanly.

## Impact

- **API**: `src/vmss_api/form_builder/service.py` (`reorder_steps`,
  `reorder_fields`), `src/vmss_api/form_builder/tests.py` (new test cases).
  No schema, migration, or route-shape changes.
- **Web**: `admin-form-builder.tsx`, `StepCard.tsx`,
  `use-admin-form-builder.ts` (step drag-and-drop wiring);
  `admin-form-builder-step-editor.tsx`, `use-admin-form-builder-step-editor.ts`,
  `FieldPropertiesPanel.tsx` (publish action + unpublished-changes indicator,
  toast copy); `VisitorInfoStep`, `VisitDetailsStep`, `VehicleInfoStep` (or
  their wizard-hook equivalents) and `use-effective-form.ts`'s consumers
  (config-driven field visibility, mirroring `CarriedItemsStep`/
  `ConsentStep`'s existing pattern) in both
  `use-visitor-request-wizard.ts` and
  `use-staff-visitor-registration-wizard.ts`.
- **No breaking changes**: every fix is additive/corrective against
  documented-but-unfinished or undocumented-but-unintended behavior; no
  existing correct behavior for any already-published, unconfigured branch
  changes.

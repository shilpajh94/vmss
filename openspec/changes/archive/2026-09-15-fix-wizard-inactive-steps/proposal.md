## Why

The admin Form Builder lets an operator deactivate a registration step (e.g. "Carried Items", "Vehicle Info") or reorder steps, and — per the form-builder capability's own spec — a step that is inactive at publish time is dropped from `GET /form-builder/effective`'s `steps` array entirely. But the visitor self-service wizard (`/visitor/request`) and the staff-assisted wizard (`/staff/visitors/new`) both render their step sidebar/stepper from a hardcoded, always-six-entry constant (`WIZARD_STEPS` / `STAFF_WIZARD_STEPS`), and switch step content with a hardcoded `currentStep === N` chain. Neither ever reads the fetched `effectiveFormSteps` to decide which steps exist. The result is exactly what was reported: toggling "Carried Items"/"Vehicle Info" to inactive and publishing has no visible effect on either wizard — every step still renders, in the same fixed order, regardless of the published config.

Root cause was confirmed by reading both layers: the backend already filters correctly at publish time (`form_builder/service.py::publish`) and the frontend's `useEffectiveForm` hook already receives a correct `isActive` flag per step — the gap is entirely in how the two wizards consume that data (or rather, don't) for step-level visibility and ordering.

## What Changes

- Both wizards derive their step list — which steps exist, their order, and their labels/icons — from the published `effectiveFormSteps` response instead of the hardcoded `WIZARD_STEPS`/`STAFF_WIZARD_STEPS` constants. A step absent from that response (inactive, or a tenant/branch that never enabled it) does not appear in the sidebar/stepper and cannot be navigated to.
- Step ordering in both wizards follows each step's `orderIndex` from the config, not the current fixed sequence.
- `currentStep` bounds, "Next"/"Back" navigation, and step-count display (e.g. "Step 3 of 6") are computed from however many steps are actually present, not a hardcoded `0..5` range.
- A registration step returned by the config with a `key` outside the six canonical steps (a custom admin-created step) is rendered generically from its field list, consistent with how "Carried Items" and "Consent Agreement" are already rendered from config-driven fields — it no longer silently disappears.
- `CarriedItemsStep` and `ConsentStep` no longer treat "this step's fields array is empty" as "config hasn't loaded yet, fall back to hardcoded defaults" — they distinguish that loading state from "this step is genuinely not part of the effective config" (which now can't happen anyway, since an inactive step is filtered out of the step list itself before either component would be asked to render).
- Out of scope (tracked separately, not touched here): making Visitor Info / Visit Info / Vehicle Info's own *field* sets config-driven. Those three steps keep their existing hardcoded fields; this change only fixes whether the step itself is shown, in what order, and — for a genuinely custom step — with a generic field renderer.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `visitor-request-wizard`: adds a requirement that the step list, order, and navigability reflect the branch's published form-builder configuration (inactive steps omitted, custom steps rendered generically), replacing the implicit assumption that all six named steps always render.
- `staff-visitor-registration`: replaces the "six-step progress stepper" requirement with the same config-driven step list/order/navigability requirement as `visitor-request-wizard`, since both wizards share this behavior and bug.

## Impact

- Affected code (both under `src/presentation/pages/`):
  - `visitor-request/types.ts` (`WIZARD_STEPS`), `visitor-request/Components/StepSidebar.tsx`, `visitor-request/visitor-request.tsx`, `visitor-request/hooks/use-visitor-request-wizard.ts`.
  - `staff-visitor-registration/types.ts` (`STAFF_WIZARD_STEPS`), `staff-visitor-registration/Components/RegistrationStepper.tsx`, `staff-visitor-registration.tsx`, `staff-visitor-registration/hooks/use-staff-visitor-registration-wizard.ts`.
  - Shared: `presentation/hooks/use-effective-form.ts` (`findStepFields` / step-presence helpers), `visitor-request/Components/steps/CarriedItemsStep.tsx` and the Consent step's equivalent (loading-vs-absent fix).
- No backend change — `VMSS_API`'s `form_builder`/`registrations` endpoints already behave correctly; this is a frontend-only fix in `VMMS_WEB`.
- No wire contract change; `FormStepOutSchema` already exposes everything needed (`key`, `isActive`, `orderIndex`, `fields`).
- Not addressed here (separate, already-tracked gap): Visitor Info / Visit Info / Vehicle Info field-level config-driven rendering, and the admin Form Builder's missing "unpublished changes" indicator.

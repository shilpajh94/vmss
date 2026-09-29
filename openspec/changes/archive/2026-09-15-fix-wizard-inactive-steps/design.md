## Context

Both wizards currently hardcode their step list (`WIZARD_STEPS` / `STAFF_WIZARD_STEPS`, both `readonly string[]` label tuples with no associated key), switch step content with a flat `currentStep === N && <Component/>` chain, and clamp `currentStep` against literal `0`/`5`. `validateStep` in both hooks also switches on the numeric step index (0, 1, 4) rather than a step key. Both hooks already fetch `effectiveFormSteps` via `useEffectiveForm(branchId)` but only use it to pull two steps' `fields` (`findStepFields(effectiveFormSteps, 'carried_items' | 'consent_agreement')`) — `isActive`, `orderIndex`, and step presence itself are never consulted. The backend's canonical step keys (confirmed in `VMSS_API/src/vmss_api/form_builder/defaults.py`) are `visitor_info`, `visit_details`, `carried_items`, `vehicle_info`, `consent_agreement`, `review_confirm`. `FormStep.key` is typed as a plain `string` in the Zod schema (`form-builder-schema.ts`), not an enum — nothing in the wire contract constrains it to this set, since a branch admin can also create a custom step.

`useEffectiveForm(branchId)` re-fetches whenever `branchId` changes, and `branchId` is derived from `formState.visitInfo.location` — a field the visitor fills in on the *second* step (Visit Info), not the first. So at wizard start (before Visit Info is completed) the hook fetches with `branchId: undefined`, which resolves to the tenant-default published config; once the visitor picks a location, the hook may refetch a branch-specific override that differs from the tenant default. This means the active step set can legitimately change mid-session. See Risks below.

See `proposal.md` for the bug and overall fix scope; see the two delta specs for the exact required behavior.

## Goals / Non-Goals

**Goals:**
- Make the step sidebar/stepper, step content routing, and step-count/navigation bounds in both wizards driven by `effectiveFormSteps` (filtered to `isActive`, ordered by `orderIndex`) instead of the hardcoded constants.
- Support an active step whose key isn't one of the six canonical keys (a custom step) by rendering it generically from its configured fields, the same way `CarriedItemsStep`/`ConsentStep` already render configured fields.
- Fix `CarriedItemsStep`/`ConsentStep`'s "empty fields ⇒ hardcoded defaults" fallback so it only fires while the config is genuinely still loading, not whenever a step's field list happens to be empty.
- Re-key `validateStep` and navigation bounds off the dynamic step list's length/keys instead of literal indices, so removing or reordering steps doesn't silently validate or render the wrong step.

**Non-Goals:**
- Making Visitor Info / Visit Info / Vehicle Info's own field sets config-driven (proposal's explicit out-of-scope item).
- Changing when/how `branchId` is resolved, or eliminating the tenant-default → branch-override refetch that can shift the step list mid-session — that behavior already exists for field-level config today and is not something this fix introduces or needs to solve to close the reported bug.
- Adding an "unpublished changes" indicator to the admin Form Builder screen (separate, already-noted gap).
- Changing the backend in any way.

## Decisions

**1. Introduce a step registry keyed by the backend's step `key`, not by array index.**
A single module (e.g. `presentation/pages/shared/registration-wizard-steps.ts`, imported by both wizards) exports:
```ts
type StepKey = 'visitor_info' | 'visit_details' | 'carried_items' | 'vehicle_info' | 'consent_agreement' | 'review_confirm'

interface StepDefinition {
  key: StepKey
  label: string          // fallback label if FormStep.name is absent/blank
  component: StepComponent
}

const CANONICAL_STEPS: Record<StepKey, StepDefinition> = { ... }
```
This mirrors the existing `STEP_ICONS: Record<string, ...>` registry pattern already used in `admin-form-builder/Components/StepCard.tsx`, so it's consistent with a convention already in the codebase rather than a new one. A step from the config whose `key` isn't in `CANONICAL_STEPS` falls back to a generic field-driven step component (see Decision 4).
- *Alternative considered*: keep per-wizard hardcoded arrays but filter them by cross-referencing `effectiveFormSteps`. Rejected — it still requires a key↔label mapping to do the cross-reference, and duplicates that mapping across two wizards for no benefit; centralizing it also removes the current byte-for-byte duplication between `WIZARD_STEPS` and `STAFF_WIZARD_STEPS`.

**2. Compute the active, ordered step list once per wizard render, from `effectiveFormSteps`.**
```ts
const activeSteps = useMemo(
  () => [...effectiveFormSteps].filter((s) => s.isActive).sort((a, b) => a.orderIndex - b.orderIndex),
  [effectiveFormSteps],
)
```
Each wizard maps `activeSteps` to `{ key, label: step.name || CANONICAL_STEPS[key]?.label, component }` for rendering, using `CANONICAL_STEPS[step.key]` when the key matches a known canonical step, otherwise the generic renderer. `currentStep` becomes an index into `activeSteps` (still a number, for minimal disruption to existing state/URL handling), and `activeSteps.length` replaces every hardcoded `6`/`5`/`0` bound in `goNext`/`goBack`/`goToStep`/footer visibility.
- *Alternative considered*: key wizard state by `StepKey` instead of numeric index throughout. Rejected for this fix — larger diff across both hooks' state shape for no behavioral gain; numeric index into a *dynamic* array already fixes the bug as long as the array itself is correct and bounds are derived from its length, not a literal.

**3. `validateStep` and other index-coupled logic switch on `activeSteps[step].key`, not the raw index.**
Both hooks' `validateStep(step, ...)` currently do `if (step === 0) {...} else if (step === 1) {...} else if (step === 4) {...}`. Since `step` will keep meaning "index into `activeSteps`" (Decision 2), the index-to-meaning mapping is no longer fixed — a branch that deactivates Visit Info shifts Carried Items from index 2 to index 1. The fix looks up `activeSteps[step]?.key` first and switches on that key, so validation stays correct regardless of which steps are active or their order.

**4. Generic step renderer for non-canonical (custom) step keys.**
A step present in `activeSteps` whose `key` has no entry in `CANONICAL_STEPS` renders via a new small component (e.g. `GenericConfiguredStep`) that maps the step's `fields` through the existing `DynamicField` component (already used inside `CarriedItemsStep`/`ConsentStep` for configured fields) and stores answers in a keyed bag on the wizard's form state (e.g. `formState.customStepAnswers[step.key][field.key]`). This is deliberately minimal — no per-field validation beyond what `DynamicField`/`isRequired` already provide — since building a full custom-step authoring/validation experience is bigger than this bug fix; it only needs to ensure a custom step doesn't silently vanish, per the spec.
- *Alternative considered*: only fix step-list *visibility* for the six canonical steps and leave a genuinely custom step unrendered (matching today's behavior) as an accepted gap. Rejected because the delta specs (and the investigation) call out custom-step disappearance as part of the same underlying defect (the step list is a hardcoded enumeration of the six keys, full stop) — fixing the enumeration mechanism but re-hardcoding it to the same six keys would leave the mechanism only partially fixed.

**5. Loading-state handling: keep the six canonical steps as a *skeleton*, never as submitted default data.**
While `useEffectiveForm` reports `isLoading: true`, `StepSidebar`/`RegistrationStepper` render a skeleton/placeholder list (visually similar to today's static list, so there's no layout flash) but the wizard does not allow "Next" past the first step, and `CarriedItemsStep`/`ConsentStep` show a loading state for their field area rather than either an empty list or `DEFAULT_ITEM_LABELS`/`DEFAULT_CONSENT_FIELDS`. Those two hardcoded fallback constants are removed once this ships — they were standing in for "config not loaded yet," which now has an explicit `isLoading` signal instead of being inferred from an empty array.
- *Alternative considered*: keep the hardcoded fallback constants as a "config fetch failed" safety net. Rejected as a silent-failure risk — `useEffectiveForm` already swallows fetch errors into `steps: []` with `isLoading: false` (see `use-effective-form.ts`); falling back to defaults in that case would silently show an admin-invisible, possibly-wrong step/field set instead of a visible error. This fix instead surfaces the fetch failure as an error state (retry affordance) rather than a silent default — a small, in-scope extension of `useEffectiveForm`'s return shape (`error: boolean`) needed to make Decision 5 meaningful.

## Risks / Trade-offs

- **[Risk]** The step list can change after the visitor completes Visit Info (branch resolves from `undefined` → a specific branch whose override differs from the tenant default), potentially shifting or removing a step the visitor has already started filling in. → **Mitigation**: out of scope to redesign branch-resolution timing (Non-Goals), but `activeSteps` is recomputed reactively either way, so a step that disappears after being active simply stops being reachable (consistent with the "deactivated step" spec scenarios) and its already-entered form-state values are harmlessly retained but not submitted, matching how an inactive field is already dropped from submission today.
- **[Risk]** Introducing `StepKey`/`CANONICAL_STEPS` and rekeying `validateStep` touches core wizard-state logic in both hooks — a regression here breaks the entire registration flow, not just the step-visibility bug. → **Mitigation**: keep `currentStep` as a plain numeric index (Decision 2) to minimize the diff to existing state/effects; add coverage for validateStep's key-based dispatch to the existing test suite for both wizards' hooks (see tasks.md), specifically for the case where a step is deactivated and validation logic must not run for the wrong index.
- **[Risk]** `GenericConfiguredStep`'s minimal validation (required-field-only) is weaker than the bespoke validation the six canonical steps have. → **Mitigation**: acceptable for this fix — a custom step is opt-in admin behavior, not the reported bug's primary path, and matching the depth of canonical-step validation for arbitrary admin-defined steps is a larger, separate effort.
- **[Trade-off]** Removing `DEFAULT_ITEM_LABELS`/`DEFAULT_CONSENT_FIELDS` means a config-fetch failure now surfaces as a visible error/retry state instead of a (silently possibly-wrong) usable form. This is an intentional trade of "always renders something" for "never silently renders the wrong thing," consistent with the spec's loading-vs-empty distinction requirement.

## Migration Plan

Frontend-only, no data migration. Roll out as a normal deploy of `VMMS_WEB`; no backend coordination needed since the API contract is unchanged. If a regression appears, revert is a plain code revert (no schema/data to roll back).

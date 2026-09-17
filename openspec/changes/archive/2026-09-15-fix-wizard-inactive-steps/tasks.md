## 1. Shared step registry and `useEffectiveForm` groundwork

- [x] 1.1 Add a `StepKey` union type (`visitor_info`, `visit_details`, `carried_items`, `vehicle_info`, `consent_agreement`, `review_confirm`) and a `CANONICAL_STEPS: Record<StepKey, StepDefinition>` registry (key, fallback label, component reference) in a shared module used by both wizards, per design Decision 1.
- [x] 1.2 Extend `useEffectiveForm` to also return an `error: boolean` (or equivalent) flag instead of silently swallowing a fetch failure into an empty `steps` array with `isLoading: false`, per design Decision 5.
- [x] 1.3 Add a shared `activeSteps` helper/hook (filter `isActive`, sort by `orderIndex`) that both wizards call on their `effectiveFormSteps`, per design Decision 2.

## 2. Generic renderer for non-canonical steps

- [x] 2.1 Add a `GenericConfiguredStep` component that renders a step's `fields` via the existing `DynamicField` component and stores answers in a keyed bag on wizard form state, per design Decision 4.
- [x] 2.2 Wire step resolution so a step whose `key` isn't in `CANONICAL_STEPS` falls back to `GenericConfiguredStep` instead of being omitted.

## 3. Visitor-request wizard (`/visitor/request`)

- [x] 3.1 Replace `WIZARD_STEPS` usage in `StepSidebar.tsx` with the computed `activeSteps` list (label + completion state), removing the direct import of the hardcoded constant.
- [x] 3.2 Replace the flat `currentStep === N && <Component/>` chain in `visitor-request.tsx` with a lookup into `activeSteps[currentStep]`'s resolved component (canonical or generic).
- [x] 3.3 Update `use-visitor-request-wizard.ts`: expose `activeSteps` from the hook; change `goNext`/`goBack`/`goToStep` bounds from literal `5`/`0` to `activeSteps.length - 1`/`0`.
- [x] 3.4 Re-key `validateStep` to switch on `activeSteps[step]?.key` instead of the literal index, per design Decision 3.
- [x] 3.5 Replace the Back/Next footer's hardcoded `currentStep < 5` / `currentStep === 0` gates with checks against `activeSteps.length`.
- [x] 3.6 Add a loading skeleton for `StepSidebar` and gate "Next" past the first step while `useEffectiveForm` reports `isLoading`, per design Decision 5.
- [x] 3.7 Add a visible error/retry state for when `useEffectiveForm` reports `error: true`, instead of any fallback default step/field set.

## 4. Carried Items and Consent step fallback fix

- [x] 4.1 Remove `DEFAULT_ITEM_LABELS`/`DEFAULT_ITEM_KEYS` fallback branch from `CarriedItemsStep.tsx`; render a loading state when the wizard-level `isLoading` is true, and render the (possibly empty) configured field list otherwise.
- [x] 4.2 Remove `DEFAULT_CONSENT_FIELDS` fallback from `ConsentStep.tsx`; apply the same loading-vs-loaded distinction as 4.1.

## 5. Staff-visitor-registration wizard (`/staff/visitors/new`)

- [x] 5.1 Replace `STAFF_WIZARD_STEPS` usage: pass the computed `activeSteps` labels into `RegistrationStepper` (already accepts a `steps` prop per design Context, so only the caller changes).
- [x] 5.2 Replace the flat `currentStep === N && <Component/>` chain in `staff-visitor-registration.tsx` with the same `activeSteps[currentStep]` lookup as task 3.2, including the "Next: {label} →" footer text that currently indexes `STAFF_WIZARD_STEPS` directly.
- [x] 5.3 Update `use-staff-visitor-registration-wizard.ts`: expose `activeSteps`; change `goNext`/`goBack` bounds from literal `5`/`0` to `activeSteps.length - 1`/`0`; confirm `reset()` still behaves correctly against a dynamic step list.
- [x] 5.4 Re-key this hook's `validateStep` to switch on `activeSteps[step]?.key`, mirroring task 3.4.
- [x] 5.5 Add the same loading/error handling as tasks 3.6/3.7 to `RegistrationStepper`'s caller.

## 6. Tests

**Skipped deliberately** — VMMS_WEB has no test framework at all (no vitest/jest,
no `test` script, zero `.test.*` files anywhere in `src/`). Writing these 7 tests
would mean standing up a test runner and React Testing Library from scratch
first, which wasn't scoped in this change's design/tasks and is a separate
piece of work. Confirmed with the user during apply (2026-09-15); revisit if/when
this repo gets a test framework.

- [ ] ~~6.1 Visitor-request wizard: a step deactivated in the effective config (e.g. Vehicle Info) is absent from the sidebar, not reachable by navigation, and the wizard proceeds directly between its active neighbors.~~
- [ ] ~~6.2 Visitor-request wizard: steps render in the effective config's `orderIndex` order when it differs from the historical default order.~~
- [ ] ~~6.3 Visitor-request wizard: a step with a non-canonical `key` renders via the generic field-driven renderer at its configured position.~~
- [ ] ~~6.4 Visitor-request wizard: `validateStep` blocks progression on the correct step after a step earlier in the sequence has been deactivated (regression guard for the index→key rekeying in Decision 3).~~
- [ ] ~~6.5 Visitor-request wizard: while `useEffectiveForm` is loading, the sidebar shows a loading state and Carried Items/Consent do not show their old hardcoded defaults.~~
- [ ] ~~6.6 Repeat 6.1-6.5 for the staff-visitor-registration wizard.~~
- [ ] ~~6.7 `useEffectiveForm`: a fetch failure surfaces via the new `error` flag rather than resolving to an empty, "successfully loaded" step list.~~

## 7. Manual verification

No browser automation tool was available in the apply session (no `chromium-cli`,
no compatible headless Chromium build for this environment, no browser MCP
tool registered) — see the apply session's report for what was verified instead
(`tsc -b`, `oxlint`, `vite build` all clean; live `GET /form-builder/effective`
against the running DDEV backend confirmed the tenant-default config already
has `carried_items`/`vehicle_info` inactive today, and the new step-derivation
logic was traced by hand against that real payload). The three tasks below
still need an actual browser click-through — not done in this session:

- [ ] 7.1 In the admin Form Builder, deactivate "Carried Items" and "Vehicle Info", publish, then confirm both `/visitor/request` and `/staff/visitors/new` skip those steps end to end (sidebar, navigation, and submission payload).
- [ ] 7.2 Reactivate a step and publish; confirm it reappears for a new wizard session.
- [ ] 7.3 Reorder active steps in the Form Builder and publish; confirm both wizards reflect the new order.

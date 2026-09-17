## 1. Shared display-formatting helper

- [x] 1.1 Add `formatDynamicFieldValue(field: FormField, value: DynamicFieldValue): string` in `VMMS_WEB/src/presentation/components/dynamic-fields/` (e.g. a new `format-dynamic-field-value.ts` alongside `DynamicField.tsx`): boolean → "Yes"/"No", `string[]` → comma-joined `prettifyKey`-formatted values, options-bearing `string` → `prettifyKey`-formatted value, plain `string` → itself, `undefined`/empty string/empty array → `'—'`.
- [ ] 1.2 Add a focused unit/component test for the helper covering each `DynamicFieldValue` shape and the empty case. **Deferred**: `VMMS_WEB` has no test framework installed at all (no vitest/jest, no test script, zero existing `*.test.ts` files) — standing one up is a separate tooling decision out of scope for this narrow display fix, not something to bolt on silently. Revisit once the repo has a test runner.

## 2. Vehicle Info step — dynamic table columns

- [x] 2.1 In `VehicleInfoStep.tsx`, render one `<th>` per field in the `customFields` prop after the existing fixed columns and before "Actions".
- [x] 2.2 Render the matching `<td>` per row using `formatDynamicFieldValue(field, vehicle.customFieldValues?.[field.key])`.
- [ ] 2.3 Manually verify in the running app: add a vehicle with a custom field value filled in, and one with it left blank (if not required) — confirm the column appears, shows the entered value, and shows `'—'` for the blank one. **Blocked in this environment**: no browser binary available in the sandbox (Playwright's `ubuntu20.04-x64` bundle isn't supported here, no system Chrome/Chromium installed) — needs a human check in an actual browser.

## 3. Review & Confirm — thread custom field metadata into props

- [x] 3.1 Add `vehicleCustomFields?: FormField[]` and `carriedItemsCustomFields?: FormField[]` (both defaulting to `[]`) to `ReviewConfirmStepProps` in `ReviewConfirmStep.tsx`.
- [x] 3.2 Add `customFieldValues: CustomFieldValues` to `ReviewableFormState`.
- [x] 3.3 Update `visitor-request.tsx` and `use-visitor-request-wizard.ts` to pass the Vehicle Info / Carried Items active field lists and `formState.customFieldValues` through to `ReviewConfirmStep`. (`formState.customFieldValues` already flowed through via `formState={formState}`; the hook already computed both field lists, so only the page-level prop passing needed adding — no hook changes required.)
- [x] 3.4 Update `staff-visitor-registration.tsx` and `use-staff-visitor-registration-wizard.ts` the same way. (Same as above — hook already exposed both field lists.)

## 4. Review & Confirm — render the values

- [x] 4.1 In the "Vehicle Info" `SummarySection`, for each vehicle append one row per active field in `vehicleCustomFields` (label from `field.label`, value via `formatDynamicFieldValue`), alongside the existing `makeModel · licensePlate` row.
- [x] 4.2 In the "Carried Items" `SummarySection`, append one row per active field in `carriedItemsCustomFields`, reading the value from `customFieldValues[field.key]` via `formatDynamicFieldValue`.
- [ ] 4.3 Manually verify: submit a visit request with a Vehicle Info custom field and a Carried Items custom field filled in — confirm both appear correctly labeled in the Review & Confirm screen before submitting, for both the public wizard (`/visitors/new` or equivalent) and the staff wizard (`/staff/visitors/new`). **Blocked in this environment** — same reason as 2.3.

## 5. Regression check

- [ ] 5.1 Confirm existing `VehicleInfoStep`/`ReviewConfirmStep`/wizard-hook tests (if any) still pass, and add/update snapshot or rendering tests covering the new columns/rows. **Deferred** — same reason as 1.2 (no test framework in this repo yet). Confirmed there are zero pre-existing test files for these components to regress.
- [x] 5.2 Confirm a branch with no admin-configured custom fields on Vehicle Info/Carried Items renders identically to before this change (no empty extra columns/rows). (Verified by code review: `vehicleCustomFields`/`carriedItemsCustomFields` default to `[]`, and every new column/row is produced by `.map()`/`.flatMap()` over that list — an empty list renders zero extra columns/rows, so behavior is unchanged when no custom fields are configured.)

## 1. Tolerant parsing

- [x] 1.1 In `form-builder-schema.ts`, default `hideLabel` to `false` and `visibilityCondition` to `null` on both group schemas (design.md Decision 1).
- [x] 1.2 Add `FormFieldListSchema`, which filters unsupported `fieldType` entries with a `console.warn` and strictly parses the rest. Use it in `FormStepOutSchema` (and so `EffectiveFormStepSchema`) and in `FormFieldListResponseSchema` (design.md Decision 2).

## 2. Verification

- [x] 2.1 Add `scripts/fixtures/effective-form-old-shape.json`, trimmed from the dev response: fields without `hideLabel`, groups without `visibilityCondition`, and one `signature_pad` field. Add `scripts/check-effective-form.ts`, which parses the fixture and, if reachable, the live `/form-builder/effective`. It asserts that parsing succeeds, the unknown field is dropped, and `hideLabel` is `false`.
- [x] 2.2 Before the API migration is applied, open `/visitor/request` and `/staff/visitors/new` via `npm run screenshots`, and confirm the steps render with no load error and no Terms & Conditions field. After the API change, confirm Terms & Conditions renders as a consent checkbox.
- [x] 2.3 `npm run build` and `npm run lint` are clean.

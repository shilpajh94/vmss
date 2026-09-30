## Context

`form-builder-schema.ts` defines strict zod objects:
- `FormFieldOutSchema.hideLabel: z.boolean()` (required);
- `EffectiveFormFieldGroupSchema.visibilityCondition:
  VisibilityConditionSchema.nullable()` (required key);
- `fieldType: FormFieldTypeSchema` (a closed enum);
- `FormStepOutSchema.fields: z.array(FormFieldOutSchema)`.

`apiClient.makeRequest({ parserSchema })` throws on any issue, and the
page hooks turn that into the load-error state. Parsing the live dev
response (saved in the API change's investigation) reproduces the 31
issues exactly.

## Goals / Non-Goals

**Goals:** one outdated key, or one unknown field, can't blank the form.
Unknown types never reach `DynamicField`.

**Non-Goals:**
- rendering unknown types generically;
- loosening validation of known fields;
- the server-side repair, which is in VMSS_API.

## Decisions

### 1. Defaults on the schema, not in components
- `hideLabel: z.boolean().default(false)` on `FormFieldOutSchema`;
- `visibilityCondition: VisibilityConditionSchema.nullable().default(null)`
  on both group schemas.

`z.infer` output types stay `boolean` and `VisibilityCondition | null`,
so no component changes.

### 2. Filter unknown field types while parsing the list
`fields: z.array(z.unknown()).transform(filterSupportedFields)`, where
`filterSupportedFields`:
1. keeps entries whose `fieldType` is in `FormFieldTypeSchema.options`,
   and `console.warn`s once per dropped entry with its `key` and
   `fieldType`;
2. parses the rest with `FormFieldOutSchema`. A known-type field that's
   otherwise malformed still fails loudly, because that's a real contract
   break.

It's exported as `FormFieldListSchema` and used by `FormStepOutSchema`,
and so by `EffectiveFormStepSchema`, and by `FormFieldListResponseSchema`.
The single-field responses (create/update) stay strict. The output type
is still `FormField[]`.

*Alternative:* `z.enum(...).catch('text')`. That would render an unknown
type as a text input the admin never configured. Rejected.

### 3. Verification without a test runner
The repo has no unit-test runner, and adding one is out of scope. Instead,
a new `scripts/check-effective-form.ts`, run with `npx tsx`, parses:
- a fixture of the old-shape snapshot (committed under
  `scripts/fixtures/`, trimmed from the dev response);
- the live `GET /form-builder/effective`, when reachable.

It asserts that parsing succeeds, the `signature_pad` field is absent,
and `hideLabel === false`. Then the screenshot pass
(`npm run screenshots`) confirms that `/visitor/request` and
`/staff/visitors/new` render steps.

## Risks / Trade-offs

- [A silently dropped field hides a misconfiguration] → A console warning
  is logged, and the API side logs at WARNING and migrates the data.
- [A group `fieldKeys` entry names a dropped field] → Group rendering
  resolves members by key, so a missing key renders nothing. Parsing
  isn't affected, since `fieldKeys` are plain strings. Group rendering
  isn't exercised without a test runner. The real `terms_conditions`
  field is ungrouped.

import z from 'zod'

// Mirrors `form_builder/schemas.py::FormFieldType` (VMSS_API) — the 14
// supported field types a step's fields can be. `dynamic_table`,
// `rich_text_block`, `signature_pad` were removed (never had capture UI,
// validation, or rendering); `checkbox_single`/`radio_button` were added —
// see openspec/changes/archive/2026-09-24-update-form-field-type-catalog/
// in VMSS_API and this repo's update-form-field-type-catalog change.
export const FormFieldTypeSchema = z.enum([
  'text',
  'email',
  'phone',
  'number',
  'dropdown_select',
  'date_picker',
  'time_picker',
  'toggle_switch',
  'checkbox_list',
  'checkbox_single',
  'radio_button',
  'file_upload',
  'textarea',
  'static_text',
])
export type FormFieldType = z.infer<typeof FormFieldTypeSchema>

export const FieldWidthSchema = z.enum(['half', 'full'])
export type FieldWidth = z.infer<typeof FieldWidthSchema>

export const ConditionOperatorSchema = z.enum(['equals', 'not_equals'])
export type ConditionOperator = z.infer<typeof ConditionOperatorSchema>

export const VisibilityConditionSchema = z.object({
  fieldKey: z.string(),
  operator: ConditionOperatorSchema,
  value: z.string(),
})
export type VisibilityCondition = z.infer<typeof VisibilityConditionSchema>

export const ValidationRulesSchema = z.object({
  minLength: z.number().nullable().optional(),
  maxLength: z.number().nullable().optional(),
  minValue: z.number().nullable().optional(),
  maxValue: z.number().nullable().optional(),
})
export type ValidationRules = z.infer<typeof ValidationRulesSchema>

export const FormFieldOutSchema = z.object({
  id: z.string(),
  stepId: z.string(),
  // Which of the step's field groups this field belongs to, or `null` for
  // an ungrouped (flat) field — mirrors `form_builder/schemas.py::FormFieldOut.group_id`
  // (add-repeatable-field-groups).
  groupId: z.string().nullable(),
  key: z.string(),
  label: z.string(),
  placeholder: z.string().nullable(),
  helpText: z.string().nullable(),
  fieldType: FormFieldTypeSchema,
  isSystem: z.boolean(),
  isLocked: z.boolean(),
  isActive: z.boolean(),
  isRequired: z.boolean(),
  options: z.array(z.string()).nullable(),
  validationRules: ValidationRulesSchema.nullable(),
  visibilityCondition: VisibilityConditionSchema.nullable(),
  width: FieldWidthSchema,
  orderIndex: z.number(),
  // When true, the visitor-facing renderer hides `label` as visible text —
  // it stays the field's accessible name (e.g. via a visually-hidden but
  // still-linked <label>) rather than disappearing from the accessibility
  // tree entirely. Purely a rendering flag; doesn't affect `isRequired`
  // enforcement. Defaults to `false`: a snapshot published before the flag
  // existed has no key at all (tolerate-unknown-form-field-types).
  hideLabel: z.boolean().default(false),
})
export type FormField = z.infer<typeof FormFieldOutSchema>

const SUPPORTED_FIELD_TYPES: ReadonlySet<string> = new Set(FormFieldTypeSchema.options)

function isSupportedFieldType(entry: unknown): boolean {
  const fieldType = (entry as { fieldType?: unknown } | null)?.fieldType
  return typeof fieldType === 'string' && SUPPORTED_FIELD_TYPES.has(fieldType)
}

// A step's field list, tolerant of one kind of drift: a field whose type the
// client doesn't support (e.g. one removed from the catalog after it was
// saved) is dropped with a warning instead of failing the whole form. A
// known-type field that's otherwise malformed still fails loudly — that's a
// real contract break (tolerate-unknown-form-field-types design.md Decision 2).
export const FormFieldListSchema = z
  .array(z.unknown())
  .transform((entries) =>
    entries.filter((entry) => {
      if (isSupportedFieldType(entry)) return true
      const { key, fieldType } = (entry ?? {}) as { key?: unknown; fieldType?: unknown }
      console.warn(`Skipping form field ${String(key)} with unsupported type ${String(fieldType)}`)
      return false
    }),
  )
  .pipe(z.array(FormFieldOutSchema))

// Mirrors `form_builder/schemas.py::FormFieldGroupOut` — an admin-defined,
// optionally repeatable named block of a step's fields (e.g. the seeded
// "vehicles"/"visitors" groups, or a custom one like "parcels"). `fieldIds`
// lists the step's fields currently assigned to it, in the admin-editor
// (draft) shape — see `EffectiveFormFieldGroupSchema` below for the
// published-snapshot shape, which addresses fields by key instead.
// `visibilityCondition` (add-conditional-field-groups) mirrors a
// `FormField`'s own — it references another field on the *same step* and,
// when present, gates the whole group (and every field inside it).
export const FormFieldGroupOutSchema = z.object({
  id: z.string(),
  stepId: z.string(),
  key: z.string(),
  name: z.string(),
  isSystem: z.boolean(),
  isLocked: z.boolean(),
  isRepeatable: z.boolean(),
  minInstances: z.number().nullable(),
  maxInstances: z.number().nullable(),
  orderIndex: z.number(),
  fieldIds: z.array(z.string()),
  visibilityCondition: VisibilityConditionSchema.nullable().default(null),
})
export type FormFieldGroup = z.infer<typeof FormFieldGroupOutSchema>

export const FormStepOutSchema = z.object({
  id: z.string(),
  branchId: z.string().nullable(),
  key: z.string(),
  name: z.string(),
  description: z.string().nullable(),
  icon: z.string().nullable(),
  isSystem: z.boolean(),
  isLocked: z.boolean(),
  isActive: z.boolean(),
  orderIndex: z.number(),
  fields: FormFieldListSchema,
  groups: z.array(FormFieldGroupOutSchema),
})
export type FormStep = z.infer<typeof FormStepOutSchema>

export const FormStepListResponseSchema = z.object({
  success: z.boolean(),
  message: z.string(),
  data: z.array(FormStepOutSchema),
})

export const FormStepResponseSchema = z.object({
  success: z.boolean(),
  message: z.string(),
  data: FormStepOutSchema,
})

export const FormFieldListResponseSchema = z.object({
  success: z.boolean(),
  message: z.string(),
  data: FormFieldListSchema,
})

export const FormFieldResponseSchema = z.object({
  success: z.boolean(),
  message: z.string(),
  data: FormFieldOutSchema,
})

export const FormFieldGroupListResponseSchema = z.object({
  success: z.boolean(),
  message: z.string(),
  data: z.array(FormFieldGroupOutSchema),
})

export const FormFieldGroupResponseSchema = z.object({
  success: z.boolean(),
  message: z.string(),
  data: FormFieldGroupOutSchema,
})

// --- Published (effective-form) snapshot shapes ---
//
// `GET /form-builder/effective` (`form_builder/service.py::_step_to_snapshot`)
// returns a plain JSON snapshot, not the same `FormFieldGroupOut` shape the
// admin-editor endpoints use: a group's fields are addressed by `fieldKeys`
// there, not `fieldIds` (matching how the snapshot's own `fields[]` are also
// keyed, not id-referenced, elsewhere). Everything else about a step/field is
// identical to the draft shapes above, so only the group shape needs its own
// schema.
export const EffectiveFormFieldGroupSchema = z.object({
  id: z.string(),
  stepId: z.string(),
  key: z.string(),
  name: z.string(),
  isSystem: z.boolean(),
  isLocked: z.boolean(),
  isRepeatable: z.boolean(),
  minInstances: z.number().nullable(),
  maxInstances: z.number().nullable(),
  orderIndex: z.number(),
  fieldKeys: z.array(z.string()),
  // Absent from snapshots published before conditional groups existed.
  visibilityCondition: VisibilityConditionSchema.nullable().default(null),
})
export type EffectiveFormFieldGroup = z.infer<typeof EffectiveFormFieldGroupSchema>

export const EffectiveFormStepSchema = FormStepOutSchema.extend({
  groups: z.array(EffectiveFormFieldGroupSchema),
})
export type EffectiveFormStep = z.infer<typeof EffectiveFormStepSchema>

export const EffectiveFormStepListResponseSchema = z.object({
  success: z.boolean(),
  message: z.string(),
  data: z.array(EffectiveFormStepSchema),
})

export const PublishResultSchema = z.object({
  branchId: z.string().nullable(),
  version: z.number(),
  publishedAt: z.string(),
})
export type PublishResult = z.infer<typeof PublishResultSchema>

export const PublishResponseSchema = z.object({
  success: z.boolean(),
  message: z.string(),
  data: PublishResultSchema,
})

// --- Request-side input shapes (form_builder/schemas.py's Create/Update) ---

export interface FormStepCreateInput {
  key: string
  name: string
  description?: string
  icon?: string
}

export interface FormStepUpdateInput {
  name?: string
  description?: string
  icon?: string
  isActive?: boolean
}

export interface FormFieldCreateInput {
  key: string
  label: string
  placeholder?: string
  helpText?: string
  fieldType: FormFieldType
  isRequired?: boolean
  // Which of the step's field groups to assign this field to at creation,
  // or omit to leave it ungrouped.
  groupId?: string
  options?: string[]
  validationRules?: ValidationRules
  visibilityCondition?: VisibilityCondition
  width?: FieldWidth
  hideLabel?: boolean
}

export interface FormFieldUpdateInput {
  fieldType?: FormFieldType
  label?: string
  placeholder?: string
  helpText?: string
  isActive?: boolean
  isRequired?: boolean
  // `null` moves the field back to ungrouped; omit to leave its current
  // group assignment unchanged.
  groupId?: string | null
  options?: string[] | null
  validationRules?: ValidationRules | null
  visibilityCondition?: VisibilityCondition | null
  width?: FieldWidth
  hideLabel?: boolean
}

export interface FormFieldGroupCreateInput {
  key: string
  name: string
  isRepeatable?: boolean
  minInstances?: number
  maxInstances?: number
  visibilityCondition?: VisibilityCondition
}

export interface FormFieldGroupUpdateInput {
  name?: string
  isRepeatable?: boolean
  minInstances?: number | null
  maxInstances?: number | null
  // `null` clears the group's condition (always visible); omit to leave its
  // current condition unchanged — same convention as `FormFieldUpdateInput`.
  visibilityCondition?: VisibilityCondition | null
}

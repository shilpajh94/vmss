import z from 'zod'

// Mirrors `form_builder/schemas.py::FormFieldType` (VMSS_API) — the 14
// supported field types a step's fields can be.
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
  'file_upload',
  'textarea',
  'dynamic_table',
  'rich_text_block',
  'signature_pad',
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
})
export type FormField = z.infer<typeof FormFieldOutSchema>

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
  fields: z.array(FormFieldOutSchema),
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
  data: z.array(FormFieldOutSchema),
})

export const FormFieldResponseSchema = z.object({
  success: z.boolean(),
  message: z.string(),
  data: FormFieldOutSchema,
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
  options?: string[]
  validationRules?: ValidationRules
  visibilityCondition?: VisibilityCondition
  width?: FieldWidth
}

export interface FormFieldUpdateInput {
  label?: string
  placeholder?: string
  helpText?: string
  isActive?: boolean
  isRequired?: boolean
  options?: string[] | null
  validationRules?: ValidationRules | null
  visibilityCondition?: VisibilityCondition | null
  width?: FieldWidth
}

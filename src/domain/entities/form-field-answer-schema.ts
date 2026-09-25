import z from "zod"

// Shared wire shapes for admin-authored (form-builder) field answers across
// the walk-in and staff invitation contracts — addressed by the field's
// UUID `id`, never its `key` slug (see form-builder-schema.ts's `FormField`).
export const FieldAnswerSchema = z.object({
  fieldId: z.string().min(1),
  value: z.unknown(),
})
export type FieldAnswer = z.infer<typeof FieldAnswerSchema>

export const ConsentAnswerSchema = z.object({
  fieldId: z.string().min(1),
  accepted: z.boolean(),
})
export type ConsentAnswer = z.infer<typeof ConsentAnswerSchema>

export const GroupAnswerSchema = z.object({
  groupId: z.string().min(1),
  instances: z.array(z.array(FieldAnswerSchema)),
})
export type GroupAnswer = z.infer<typeof GroupAnswerSchema>

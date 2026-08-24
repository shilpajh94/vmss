import z from "zod"

export const VisitorCategoryOutSchema = z.object({
  id: z.string(),
  name: z.string(),
  code: z.string(),
  description: z.string().nullable(),
  badgeColor: z.enum(["blue", "orange", "gold", "grey"]),
  ndaRequirement: z.enum(["digital", "signed_pdf", "optional", "none"]).nullable(),
  escortRequirement: z.enum(["self_escort", "access_logs_only", "always_required", "gate_check_in_only"]).nullable(),
  maxDurationMinutes: z.number().nullable(),
})

export type VisitorCategoryOut = z.infer<typeof VisitorCategoryOutSchema>

export const VisitorCategoryResponseSchema = z.object({
  success: z.boolean(),
  message: z.string(),
  data: VisitorCategoryOutSchema,
})

export type VisitorCategoryResponse = z.infer<typeof VisitorCategoryResponseSchema>

export const VisitorCategoryListResponseSchema = z.object({
  success: z.boolean(),
  message: z.string(),
  data: z.array(VisitorCategoryOutSchema),
  pagination: z.object({
    page: z.number(),
    pageSize: z.number(),
    total: z.number(),
    totalPages: z.number(),
  }),
})

export type VisitorCategoryListResponse = z.infer<typeof VisitorCategoryListResponseSchema>

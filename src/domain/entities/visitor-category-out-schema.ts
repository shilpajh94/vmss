import z from "zod"

export const VisitorCategoryOutSchema = z.object({
  id: z.string(),
  name: z.string(),
  code: z.string(),
  description: z.string().nullable(),
  // Falls back to "blue" instead of rejecting the whole list: the backend has
  // pre-existing records with free-text/hex values (e.g. "#FFD700") that predate
  // this enum, and one non-conforming record must not sink every category.
  badgeColor: z.enum(["blue", "orange", "gold", "grey"]).catch("blue"),
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

export const VisitorCategoryBulkCreateItemSchema = z.object({
  name: z.string(),
  status: z.enum(["created", "skipped"]),
  reason: z.string().nullable(),
  category: VisitorCategoryOutSchema.nullable(),
})

export type VisitorCategoryBulkCreateItem = z.infer<typeof VisitorCategoryBulkCreateItemSchema>

export const VisitorCategoryBulkCreateOutSchema = z.object({
  items: z.array(VisitorCategoryBulkCreateItemSchema),
  createdCount: z.number(),
  skippedCount: z.number(),
})

export type VisitorCategoryBulkCreateOut = z.infer<typeof VisitorCategoryBulkCreateOutSchema>

export const VisitorCategoryBulkCreateResponseSchema = z.object({
  success: z.boolean(),
  message: z.string(),
  data: VisitorCategoryBulkCreateOutSchema,
})

export type VisitorCategoryBulkCreateResponse = z.infer<typeof VisitorCategoryBulkCreateResponseSchema>

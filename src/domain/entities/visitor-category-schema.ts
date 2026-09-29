import z from "zod"

export const VisitorCategorySchema = z.object({
  id: z.string().min(1),
  name: z.string().min(1),
  code: z.string().min(1),
  description: z.string().optional(),
  badgeColor: z.enum(["blue", "orange", "gold", "grey"]).default("blue"),
  ndaRequirement: z.enum(["digital", "signed_pdf", "optional", "none"]).optional(),
  escortRequirement: z.enum(["self_escort", "access_logs_only", "always_required", "gate_check_in_only"]).optional(),
  maxDurationMinutes: z.number().optional(),
})

export type VisitorCategory = z.infer<typeof VisitorCategorySchema>

export type VisitorCategoryInput = Omit<VisitorCategory, "id">

export interface VisitorCategoryBulkCreateInput {
  names: string[]
}

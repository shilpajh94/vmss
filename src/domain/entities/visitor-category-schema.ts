import z from "zod"

export const VisitorCategorySchema = z.object({
  id: z.string().min(1),
  name: z.string().min(1),
  description: z.string().optional(),
  badgeColor: z.enum(["blue", "orange", "gold", "grey"]).default("blue"),
  ndaRequired: z.string().optional(),
  escortRequired: z.string().optional(),
  maxDuration: z.string().optional(),
})

export type VisitorCategory = z.infer<typeof VisitorCategorySchema>

export type VisitorCategoryInput = Omit<VisitorCategory, "id">

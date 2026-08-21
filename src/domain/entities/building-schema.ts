import z from "zod"

export const BuildingSchema = z.object({
  id: z.string().min(1),
  branchId: z.string().min(1),
  branchName: z.string(),
  name: z.string().min(1),
  code: z.string().min(1),
  address: z.string(),
  isActive: z.boolean(),
})

export type Building = z.infer<typeof BuildingSchema>

export type BuildingInput = Omit<Building, "id" | "branchName">

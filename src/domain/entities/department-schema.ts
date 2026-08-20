import z from "zod"

export const DepartmentSchema = z.object({
  id: z.string().min(1),
  branchId: z.string().min(1),
  branchName: z.string(),
  floorId: z.string().optional(),
  name: z.string().min(1),
  code: z.string().min(1),
  isActive: z.boolean(),
  headOfDepartmentUserId: z.string().optional(),
  description: z.string().optional(),
})

export type Department = z.infer<typeof DepartmentSchema>

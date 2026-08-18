import z from "zod"

export const DepartmentSchema = z.object({
  id: z.string().min(1),
  name: z.string().min(1),
  branchId: z.string().min(1),
  branchName: z.string().min(1),
  headOfDepartment: z.string().optional(),
  description: z.string().optional(),
  status: z.enum(["active", "inactive"]),
  employeeCount: z.number(),
})

export type Department = z.infer<typeof DepartmentSchema>

export const DepartmentInputSchema = DepartmentSchema.pick({
  name: true,
  branchId: true,
  headOfDepartment: true,
  description: true,
  status: true,
})

export type DepartmentInput = z.infer<typeof DepartmentInputSchema>

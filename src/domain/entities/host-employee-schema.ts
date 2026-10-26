import z from "zod"

export const BranchRoleAssignmentSchema = z.object({
  id: z.string(),
  roleName: z.string(),
  branchId: z.string().optional(),
})

export type BranchRoleAssignment = z.infer<typeof BranchRoleAssignmentSchema>

export const HostEmployeeSchema = z.object({
  id: z.string().min(1),
  fullName: z.string().min(1),
  email: z.string().min(1),
  employeeCode: z.string().optional(),
  phoneNumber: z.string().optional(),
  designation: z.string().optional(),
  departmentId: z.string().optional(),
  isActive: z.boolean(),
  avatarUrl: z.string().optional(),
  branchRoles: z.array(BranchRoleAssignmentSchema),
})

export type HostEmployee = z.infer<typeof HostEmployeeSchema>

export const HostEmployeeCreateInputSchema = z.object({
  fullName: z.string().min(1),
  email: z.string().min(1),
  employeeCode: z.string().min(1),
  phoneNumber: z.string().optional(),
  designation: z.string().optional(),
  departmentId: z.string().optional(),
  roleId: z.string().optional(),
  branchId: z.string().optional(),
  password: z.string().optional(),
})

export type HostEmployeeCreateInput = z.infer<typeof HostEmployeeCreateInputSchema>

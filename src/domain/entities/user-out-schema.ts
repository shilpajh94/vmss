import z from "zod"

export const BranchRoleSchema = z.object({
  id: z.string(),
  roleName: z.string(),
  branchId: z.string().nullable(),
  // Only on `/auth/me`: every code the role grants.
  permissionCodes: z.array(z.string()).optional(),
})

export type BranchRole = z.infer<typeof BranchRoleSchema>

export const BranchRoleResponseSchema = z.object({
  success: z.boolean(),
  message: z.string(),
  data: BranchRoleSchema,
})

export type BranchRoleResponse = z.infer<typeof BranchRoleResponseSchema>

export const UserOutSchema = z.object({
  id: z.string(),
  email: z.string().email(),
  fullName: z.string(),
  isActive: z.boolean(),
  branchRoles: z.array(BranchRoleSchema),
})

export type UserOut = z.infer<typeof UserOutSchema>

export const UserOutResponseSchema = z.object({
  success: z.boolean(),
  message: z.string(),
  data: UserOutSchema,
})

export type UserOutResponse = z.infer<typeof UserOutResponseSchema>

import z from "zod"
import { PaginationMetaSchema } from "./pagination-meta-schema"
import { BranchRoleSchema } from "./user-out-schema"

export const EmployeeOutSchema = z.object({
  id: z.string(),
  email: z.string(),
  fullName: z.string(),
  employeeCode: z.string().nullable(),
  phoneNumber: z.string().nullable(),
  designation: z.string().nullable(),
  departmentId: z.string().nullable(),
  isActive: z.boolean(),
  avatarUrl: z.string().nullable(),
  branchRoles: z.array(BranchRoleSchema),
})

export type EmployeeOut = z.infer<typeof EmployeeOutSchema>

export const EmployeeListResponseSchema = z.object({
  success: z.boolean(),
  message: z.string(),
  data: z.array(EmployeeOutSchema),
  pagination: PaginationMetaSchema,
})

export const EmployeeResponseSchema = z.object({
  success: z.boolean(),
  message: z.string(),
  data: EmployeeOutSchema,
})

export type EmployeeListResponse = z.infer<typeof EmployeeListResponseSchema>

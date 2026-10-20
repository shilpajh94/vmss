import z from "zod"
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
  pagination: z.object({
    page: z.number(),
    pageSize: z.number(),
    total: z.number(),
    totalPages: z.number(),
  }),
})

export type EmployeeListResponse = z.infer<typeof EmployeeListResponseSchema>

// Single-employee envelope returned by the per-employee disable/enable actions.
export const EmployeeResponseSchema = z.object({
  success: z.boolean(),
  message: z.string(),
  data: EmployeeOutSchema,
})

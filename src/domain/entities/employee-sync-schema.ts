import z from "zod"

export const EmployeeSyncItemSchema = z.object({
  email: z.string(),
  fullName: z.string(),
  employeeCode: z.string(),
  phoneNumber: z.string().nullable().optional(),
  designation: z.string().nullable().optional(),
  departmentId: z.string().nullable().optional(),
})

export type EmployeeSyncItem = z.infer<typeof EmployeeSyncItemSchema>

export const EmployeeSyncResultSchema = z.object({
  created: z.array(z.string()),
  updated: z.array(z.string()),
  deactivated: z.array(z.string()),
})

export const EmployeeSyncResponseSchema = z.object({
  success: z.boolean(),
  message: z.string(),
  data: EmployeeSyncResultSchema,
})

export type EmployeeSyncResponse = z.infer<typeof EmployeeSyncResponseSchema>

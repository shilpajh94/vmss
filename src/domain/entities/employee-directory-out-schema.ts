import z from "zod"

export const EmployeeDirectoryOutSchema = z.object({
  id: z.string(),
  fullName: z.string(),
  designation: z.string().nullable(),
  departmentId: z.string().nullable(),
})

export type EmployeeDirectoryOut = z.infer<typeof EmployeeDirectoryOutSchema>

export const EmployeeDirectoryListResponseSchema = z.object({
  success: z.boolean(),
  message: z.string(),
  data: z.array(EmployeeDirectoryOutSchema),
  pagination: z.object({
    page: z.number(),
    pageSize: z.number(),
    total: z.number(),
    totalPages: z.number(),
  }),
})

export type EmployeeDirectoryListResponse = z.infer<typeof EmployeeDirectoryListResponseSchema>

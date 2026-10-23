import z from "zod"
import { PaginationMetaSchema } from "./pagination-meta-schema"

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
  pagination: PaginationMetaSchema,
})

export type EmployeeDirectoryListResponse = z.infer<typeof EmployeeDirectoryListResponseSchema>

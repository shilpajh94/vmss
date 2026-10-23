import z from "zod"
import { PaginationMetaSchema } from "./pagination-meta-schema"

export const DepartmentOutSchema = z.object({
  id: z.string(),
  branchId: z.string(),
  floorId: z.string().nullable(),
  name: z.string(),
  code: z.string(),
  isActive: z.boolean(),
  headOfDepartmentUserId: z.string().nullable(),
  description: z.string().nullable(),
})

export type DepartmentOut = z.infer<typeof DepartmentOutSchema>

export const DepartmentResponseSchema = z.object({
  success: z.boolean(),
  message: z.string(),
  data: DepartmentOutSchema,
})

export type DepartmentResponse = z.infer<typeof DepartmentResponseSchema>

export const DepartmentListResponseSchema = z.object({
  success: z.boolean(),
  message: z.string(),
  data: z.array(DepartmentOutSchema),
  pagination: PaginationMetaSchema,
})

export type DepartmentListResponse = z.infer<typeof DepartmentListResponseSchema>

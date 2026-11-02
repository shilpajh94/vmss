import z from "zod"
import { PaginationMetaSchema } from "./pagination-meta-schema"

export const RoleOutSchema = z.object({
  id: z.string(),
  name: z.string(),
  description: z.string().nullable(),
  permissionCodes: z.array(z.string()),
  isStandard: z.boolean(),
})

export type RoleOut = z.infer<typeof RoleOutSchema>

export interface RoleCreateInput {
  name: string
  description?: string
  permissionCodes: string[]
}

export const RoleListResponseSchema = z.object({
  success: z.boolean(),
  message: z.string(),
  data: z.array(RoleOutSchema),
  pagination: PaginationMetaSchema,
})

export type RoleListResponse = z.infer<typeof RoleListResponseSchema>

export const RoleResponseSchema = z.object({
  success: z.boolean(),
  message: z.string(),
  data: RoleOutSchema,
})

export type RoleResponse = z.infer<typeof RoleResponseSchema>

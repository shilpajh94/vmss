import z from "zod"
import { PaginationMetaSchema } from "./pagination-meta-schema"

export const PermissionOutSchema = z.object({
  code: z.string(),
  description: z.string(),
})

export type PermissionOut = z.infer<typeof PermissionOutSchema>

export const PermissionListResponseSchema = z.object({
  success: z.boolean(),
  message: z.string(),
  data: z.array(PermissionOutSchema),
  pagination: PaginationMetaSchema,
})

export type PermissionListResponse = z.infer<typeof PermissionListResponseSchema>

export const RolePermissionResyncEntrySchema = z.object({
  roleName: z.string(),
  grantedPermissionCodes: z.array(z.string()),
})

export type RolePermissionResyncEntry = z.infer<typeof RolePermissionResyncEntrySchema>

export const RolePermissionResyncResponseSchema = z.object({
  success: z.boolean(),
  message: z.string(),
  data: z.array(RolePermissionResyncEntrySchema),
})

export type RolePermissionResyncResponse = z.infer<typeof RolePermissionResyncResponseSchema>

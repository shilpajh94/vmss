import z from "zod"

export const RoleOutSchema = z.object({
  id: z.string(),
  name: z.string(),
  description: z.string().nullable(),
  permissionCodes: z.array(z.string()),
  isStandard: z.boolean(),
})

export type RoleOut = z.infer<typeof RoleOutSchema>

export const RoleListResponseSchema = z.object({
  success: z.boolean(),
  message: z.string(),
  data: z.array(RoleOutSchema),
  pagination: z.object({
    page: z.number(),
    pageSize: z.number(),
    total: z.number(),
    totalPages: z.number(),
  }),
})

export type RoleListResponse = z.infer<typeof RoleListResponseSchema>

import z from "zod"

export const BuildingOutSchema = z.object({
  id: z.string(),
  branchId: z.string(),
  name: z.string(),
  code: z.string(),
  address: z.string().nullable(),
  isActive: z.boolean(),
})

export type BuildingOut = z.infer<typeof BuildingOutSchema>

export const BuildingResponseSchema = z.object({
  success: z.boolean(),
  message: z.string(),
  data: BuildingOutSchema,
})

export type BuildingResponse = z.infer<typeof BuildingResponseSchema>

export const BuildingListResponseSchema = z.object({
  success: z.boolean(),
  message: z.string(),
  data: z.array(BuildingOutSchema),
  pagination: z.object({
    page: z.number(),
    pageSize: z.number(),
    total: z.number(),
    totalPages: z.number(),
  }),
})

export type BuildingListResponse = z.infer<typeof BuildingListResponseSchema>

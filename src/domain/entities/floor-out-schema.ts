import z from "zod"

export const FloorOutSchema = z.object({
  id: z.string(),
  buildingId: z.string(),
  name: z.string(),
  floorNumber: z.number(),
  isActive: z.boolean(),
  capacity: z.number().nullable(),
  capacityType: z.enum(["guests", "staff"]).nullable(),
  accessLevel: z.enum(["public", "restricted", "secure"]).nullable(),
})

export type FloorOut = z.infer<typeof FloorOutSchema>

export const FloorResponseSchema = z.object({
  success: z.boolean(),
  message: z.string(),
  data: FloorOutSchema,
})

export type FloorResponse = z.infer<typeof FloorResponseSchema>

export const FloorListResponseSchema = z.object({
  success: z.boolean(),
  message: z.string(),
  data: z.array(FloorOutSchema),
  pagination: z.object({
    page: z.number(),
    pageSize: z.number(),
    total: z.number(),
    totalPages: z.number(),
  }),
})

export type FloorListResponse = z.infer<typeof FloorListResponseSchema>

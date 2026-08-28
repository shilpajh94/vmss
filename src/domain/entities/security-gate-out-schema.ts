import z from "zod"

export const SecurityGateOutSchema = z.object({
  id: z.string(),
  branchId: z.string(),
  buildingId: z.string().nullable(),
  name: z.string(),
  code: z.string(),
  gateType: z.enum(["entry", "exit", "both"]),
  highSecurity: z.boolean(),
})

export type SecurityGateOut = z.infer<typeof SecurityGateOutSchema>

export const SecurityGateResponseSchema = z.object({
  success: z.boolean(),
  message: z.string(),
  data: SecurityGateOutSchema,
})

export type SecurityGateResponse = z.infer<typeof SecurityGateResponseSchema>

export const SecurityGateListResponseSchema = z.object({
  success: z.boolean(),
  message: z.string(),
  data: z.array(SecurityGateOutSchema),
  pagination: z.object({
    page: z.number(),
    pageSize: z.number(),
    total: z.number(),
    totalPages: z.number(),
  }),
})

export type SecurityGateListResponse = z.infer<typeof SecurityGateListResponseSchema>

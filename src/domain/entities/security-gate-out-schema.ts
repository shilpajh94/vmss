import z from "zod"

export const SecurityGateOutSchema = z.object({
  id: z.string(),
  buildingId: z.string(),
  floorId: z.string().nullable(),
  name: z.string(),
  gateType: z.enum(["bidirectional", "entry_only", "exit_only", "high_security"]),
  authMethod: z.string().nullable(),
  connectivityStatus: z.enum(["online", "maintenance", "offline"]),
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

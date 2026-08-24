import z from "zod"

export const ReceptionDeskOutSchema = z.object({
  id: z.string(),
  floorId: z.string(),
  name: z.string(),
  code: z.string(),
  status: z.enum(["active", "maintenance", "inactive"]),
  assignedReceptionistUserId: z.string().nullable(),
  operatingHoursFrom: z.string().nullable(),
  operatingHoursTo: z.string().nullable(),
})

export type ReceptionDeskOut = z.infer<typeof ReceptionDeskOutSchema>

export const ReceptionDeskResponseSchema = z.object({
  success: z.boolean(),
  message: z.string(),
  data: ReceptionDeskOutSchema,
})

export type ReceptionDeskResponse = z.infer<typeof ReceptionDeskResponseSchema>

export const ReceptionDeskListResponseSchema = z.object({
  success: z.boolean(),
  message: z.string(),
  data: z.array(ReceptionDeskOutSchema),
  pagination: z.object({
    page: z.number(),
    pageSize: z.number(),
    total: z.number(),
    totalPages: z.number(),
  }),
})

export type ReceptionDeskListResponse = z.infer<typeof ReceptionDeskListResponseSchema>

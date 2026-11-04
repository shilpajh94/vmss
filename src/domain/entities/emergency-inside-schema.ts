import z from "zod"

export const InsideVisitorSchema = z.object({
  invitationId: z.string(),
  visitorName: z.string(),
  hostName: z.string().nullish(),
  badgeNumber: z.string().nullish(),
  enteredAt: z.string().nullish(),
})

export type InsideVisitor = z.infer<typeof InsideVisitorSchema>

export const InsideZoneSchema = z.object({
  zoneId: z.string(),
  zoneName: z.string(),
  branchId: z.string(),
  visitors: z.array(InsideVisitorSchema),
})

export type InsideZone = z.infer<typeof InsideZoneSchema>

// The report is the full emergency list and is not paginated.
export const EmergencyInsideSchema = z.object({
  zones: z.array(InsideZoneSchema),
  unzoned: z.array(InsideVisitorSchema),
  totalInside: z.number(),
})

export type EmergencyInside = z.infer<typeof EmergencyInsideSchema>

export const EmergencyInsideResponseSchema = z
  .object({ success: z.boolean(), message: z.string(), data: EmergencyInsideSchema })
  .transform((response) => response.data)

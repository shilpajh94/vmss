import z from "zod"

export const VisitRequestSummarySchema = z.object({
  id: z.string().min(1),
  reqId: z.string().min(1),
  visitorName: z.string().min(1),
  visitorInitials: z.string().min(1),
  hostName: z.string().min(1),
  scheduledAt: z.string().min(1),
  status: z.enum(["requested", "approved", "checked_in", "denied"]),
})

export type VisitRequestSummary = z.infer<typeof VisitRequestSummarySchema>

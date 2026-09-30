import z from "zod"

export const TrackingLookupResponseSchema = z.object({
  trackingId: z.string().min(1),
  statusLabel: z.string().min(1),
  statusTone: z.enum(["success", "warning", "danger", "info"]),
  requestedDate: z.string().min(1),
  assignedHost: z.string().min(1),
  totalVisitors: z.number(),
  timelineStage: z.enum(["submitted", "under-review", "approved", "visit-day"]),
  primaryContactFullName: z.string().min(1),
})

export type TrackingLookupResponse = z.infer<typeof TrackingLookupResponseSchema>

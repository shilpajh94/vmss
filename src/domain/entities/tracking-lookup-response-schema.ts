import z from "zod"

export const TrackingLookupResponseSchema = z.object({
  trackingId: z.string().min(1),
  statusLabel: z.string().min(1),
  statusTone: z.enum(["success", "warning", "danger", "info", "neutral"]),
  requestedDate: z.string().min(1),
  assignedHost: z.string().min(1),
  totalVisitors: z.number(),
  // The step in progress; `complete` once checked out, `unknown` for a
  // status this page doesn't recognise (no step is highlighted).
  timelineStage: z.enum(["approved", "checked-in", "checked-out", "complete", "unknown"]),
  primaryContactFullName: z.string().min(1),
})

export type TrackingLookupResponse = z.infer<typeof TrackingLookupResponseSchema>

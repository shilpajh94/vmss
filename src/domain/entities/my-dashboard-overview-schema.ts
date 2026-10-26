import z from "zod"

// `GET /admin/dashboard/my-overview` — counted only over the caller's
// relevantToMe invitations, so a host's dashboard always agrees with their board.
export const MyUpcomingVisitorSchema = z.object({
  id: z.string().min(1),
  trackingId: z.string().min(1),
  primaryContactFullName: z.string().min(1),
  preferredVisitDate: z.string().nullable(),
  preferredVisitTime: z.string().nullable(),
  purposeOfVisit: z.string().nullable(),
  expiresAt: z.string().min(1),
})

export const MyDashboardOverviewSchema = z.object({
  visitsToday: z.number(),
  insideNow: z.number(),
  // Submitted and not yet expired; the deprecated `awaitingApproval` isn't read.
  openAwaitingApproval: z.number(),
  upcoming: z.number(),
  upcomingPreview: z.array(MyUpcomingVisitorSchema),
  today: z.string().min(1),
  generatedAt: z.string().min(1),
})

export type MyUpcomingVisitor = z.infer<typeof MyUpcomingVisitorSchema>
export type MyDashboardOverview = z.infer<typeof MyDashboardOverviewSchema>

export const MyDashboardOverviewResponseSchema = z.object({
  success: z.boolean(),
  message: z.string(),
  data: MyDashboardOverviewSchema,
})

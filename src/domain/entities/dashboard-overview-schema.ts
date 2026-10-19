import z from "zod"

export const DashboardUpcomingVisitorSchema = z.object({
  id: z.string().min(1),
  trackingId: z.string().min(1),
  primaryContactFullName: z.string().min(1),
  hostId: z.string().nullable(),
  hostFullName: z.string().nullable(),
  purposeOfVisit: z.string().nullable(),
  preferredVisitDate: z.string().nullable(),
  preferredVisitTime: z.string().nullable(),
  expiresAt: z.string().min(1),
})

// `visitsTodayCount` (invitations created today) is deprecated API-side and
// deliberately not read here — "Expected today" is `scheduledTodayCount`.
export const DashboardOverviewSchema = z.object({
  scheduledTodayCount: z.number(),
  checkedInTodayCount: z.number(),
  checkedInCount: z.number(),
  pendingApprovalCount: z.number(),
  oldestPendingSubmittedAt: z.string().nullable(),
  upcomingVisitorCount: z.number(),
  upcomingVisitors: z.array(DashboardUpcomingVisitorSchema),
  today: z.string().min(1),
  generatedAt: z.string().min(1),
})

export type DashboardUpcomingVisitor = z.infer<typeof DashboardUpcomingVisitorSchema>
export type DashboardOverview = z.infer<typeof DashboardOverviewSchema>

export const DashboardOverviewResponseSchema = z.object({
  success: z.boolean(),
  message: z.string(),
  data: DashboardOverviewSchema,
})

export type DashboardOverviewResponse = z.infer<typeof DashboardOverviewResponseSchema>

import z from "zod"

export const DashboardKpiSchema = z.object({
  key: z.string().min(1),
  label: z.string().min(1),
  value: z.string().min(1),
})

export const DashboardUpcomingVisitorSchema = z.object({
  id: z.string().min(1),
  trackingId: z.string().min(1),
  primaryContactFullName: z.string().min(1),
  hostId: z.string().nullable(),
  purposeOfVisit: z.string().nullable(),
  expiresAt: z.string().min(1),
})

export const DashboardOverviewSchema = z.object({
  visitsTodayCount: z.number(),
  checkedInCount: z.number(),
  pendingApprovalCount: z.number(),
  upcomingVisitorCount: z.number(),
  upcomingVisitors: z.array(DashboardUpcomingVisitorSchema),
})

export type DashboardKpi = z.infer<typeof DashboardKpiSchema>
export type DashboardUpcomingVisitor = z.infer<typeof DashboardUpcomingVisitorSchema>
export type DashboardOverview = z.infer<typeof DashboardOverviewSchema>

export const DashboardOverviewResponseSchema = z.object({
  success: z.boolean(),
  message: z.string(),
  data: DashboardOverviewSchema,
})

export type DashboardOverviewResponse = z.infer<typeof DashboardOverviewResponseSchema>

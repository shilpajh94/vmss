import z from "zod"

export const DashboardKpiSchema = z.object({
  key: z.string().min(1),
  label: z.string().min(1),
  value: z.string().min(1),
  trendCaption: z.string().min(1),
  trendDirection: z.enum(["up", "down"]),
})

export const DashboardTrafficPointSchema = z.object({
  day: z.string().min(1),
  count: z.number(),
})

export const DashboardRecentCheckinSchema = z.object({
  id: z.string().min(1),
  visitorName: z.string().min(1),
  hostName: z.string().min(1),
  time: z.string().min(1),
  badgeNumber: z.string().min(1),
  status: z.enum(["checked-in", "checked-out"]),
})

export const DashboardDepartmentBreakdownSchema = z.object({
  name: z.string().min(1),
  count: z.number(),
  percentage: z.number(),
})

export const DashboardUpcomingVisitorSchema = z.object({
  id: z.string().min(1),
  time: z.string().min(1),
  visitorName: z.string().min(1),
  company: z.string().min(1),
  hostName: z.string().min(1),
  purpose: z.string().min(1),
})

export const DashboardOverviewSchema = z.object({
  kpis: z.array(DashboardKpiSchema),
  trafficSeries: z.array(DashboardTrafficPointSchema),
  recentCheckins: z.array(DashboardRecentCheckinSchema),
  departmentBreakdown: z.array(DashboardDepartmentBreakdownSchema),
  activeDepartmentCount: z.number(),
  upcomingVisitors: z.array(DashboardUpcomingVisitorSchema),
})

export type DashboardKpi = z.infer<typeof DashboardKpiSchema>
export type DashboardTrafficPoint = z.infer<typeof DashboardTrafficPointSchema>
export type DashboardRecentCheckin = z.infer<typeof DashboardRecentCheckinSchema>
export type DashboardDepartmentBreakdown = z.infer<typeof DashboardDepartmentBreakdownSchema>
export type DashboardUpcomingVisitor = z.infer<typeof DashboardUpcomingVisitorSchema>
export type DashboardOverview = z.infer<typeof DashboardOverviewSchema>

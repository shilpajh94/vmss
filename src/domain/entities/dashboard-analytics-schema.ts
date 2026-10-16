import z from "zod"

// `GET /admin/dashboard/analytics` and `/my-analytics`. Every series arrives
// zero-filled and fixed-length from the API, so charts never fill gaps.
export const DashboardRangeSchema = z.enum(["7d", "30d"])

export const DailyTrendPointSchema = z.object({
  date: z.string().min(1),
  scheduled: z.number(),
  checkedIn: z.number(),
  noShow: z.number(),
})

export const StatusCountSchema = z.object({
  status: z.string().min(1),
  count: z.number(),
})

export const HourlyCheckInsSchema = z.object({
  hour: z.number(),
  count: z.number(),
})

export const LabelCountSchema = z.object({
  label: z.string().min(1),
  count: z.number(),
})

export const MyDashboardAnalyticsSchema = z.object({
  range: DashboardRangeSchema,
  timezone: z.string().min(1),
  today: z.string().min(1),
  generatedAt: z.string().min(1),
  dailyTrend: z.array(DailyTrendPointSchema),
  statusBreakdown: z.array(StatusCountSchema),
})

export const DashboardAnalyticsSchema = MyDashboardAnalyticsSchema.extend({
  hourlyCheckInsToday: z.array(HourlyCheckInsSchema),
  topPurposes: z.array(LabelCountSchema),
  topDepartments: z.array(LabelCountSchema),
})

export type DashboardRange = z.infer<typeof DashboardRangeSchema>
export type DailyTrendPoint = z.infer<typeof DailyTrendPointSchema>
export type StatusCount = z.infer<typeof StatusCountSchema>
export type HourlyCheckIns = z.infer<typeof HourlyCheckInsSchema>
export type LabelCount = z.infer<typeof LabelCountSchema>
export type MyDashboardAnalytics = z.infer<typeof MyDashboardAnalyticsSchema>
export type DashboardAnalytics = z.infer<typeof DashboardAnalyticsSchema>

export const DashboardAnalyticsResponseSchema = z.object({
  success: z.boolean(),
  message: z.string(),
  data: DashboardAnalyticsSchema,
})

export const MyDashboardAnalyticsResponseSchema = z.object({
  success: z.boolean(),
  message: z.string(),
  data: MyDashboardAnalyticsSchema,
})

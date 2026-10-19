import z from "zod"
import { PaginationMetaSchema } from "./pagination-meta-schema"

export const DashboardRecentCheckinSchema = z.object({
  id: z.string().min(1),
  trackingId: z.string().min(1),
  primaryContactFullName: z.string().min(1),
  hostId: z.string().nullable(),
  hostFullName: z.string().nullable(),
  status: z.string().min(1),
  checkedInAt: z.string().nullable(),
  checkedOutAt: z.string().nullable(),
})

export type DashboardRecentCheckin = z.infer<typeof DashboardRecentCheckinSchema>

export const DashboardRecentCheckinListResponseSchema = z.object({
  success: z.boolean(),
  message: z.string(),
  data: z.array(DashboardRecentCheckinSchema),
  pagination: PaginationMetaSchema,
})

export type DashboardRecentCheckinListResponse = z.infer<typeof DashboardRecentCheckinListResponseSchema>

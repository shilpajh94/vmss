import z from "zod"
import { PaginationMetaSchema } from "./pagination-meta-schema"

// `GET /invitations/calendar` (add-staff-calendar). The API decides which
// visits the caller sees (`scope`); the page renders them as-is. `days` is
// zero-filled and exact even when `events` is `truncated`.
export const CalendarScopeSchema = z.enum(["mine", "branch"])

export const CalendarDaySchema = z.object({
  date: z.string().min(1),
  total: z.number(),
})

export const CalendarEventSchema = z.object({
  id: z.string().min(1),
  trackingId: z.string().min(1),
  // Kept a plain string so a status added later degrades to a neutral chip
  // instead of failing the whole feed.
  status: z.string().min(1),
  source: z.string().min(1),
  date: z.string().min(1),
  time: z.string().nullable(),
  expectedDuration: z.string().nullable(),
  checkedInAt: z.string().nullable(),
  checkedOutAt: z.string().nullable(),
  primaryContactFullName: z.string(),
  visitorCount: z.number(),
  hostId: z.string().nullable(),
  hostFullName: z.string().nullable(),
  branchId: z.string().min(1),
  branchName: z.string().nullable(),
  buildingName: z.string().nullable(),
  purposeOfVisit: z.string().nullable(),
  visitorCategoryName: z.string().nullable(),
  visitorCategoryBadgeColor: z.string().nullable(),
})

export const CalendarFeedSchema = z.object({
  scope: CalendarScopeSchema,
  timezone: z.string().min(1),
  from: z.string().min(1),
  to: z.string().min(1),
  generatedAt: z.string().min(1),
  days: z.array(CalendarDaySchema),
  events: z.array(CalendarEventSchema),
  truncated: z.boolean(),
})

export const CalendarFeedResponseSchema = z.object({
  success: z.boolean(),
  message: z.string(),
  data: CalendarFeedSchema,
})

// `GET /invitations/calendar/day`: one page of a day's events in the
// standard order, with the day's exact total.
export const CalendarDayPageResponseSchema = z.object({
  success: z.boolean(),
  message: z.string(),
  data: z.array(CalendarEventSchema),
  pagination: PaginationMetaSchema,
})

export type CalendarScope = z.infer<typeof CalendarScopeSchema>
export type CalendarDay = z.infer<typeof CalendarDaySchema>
export type CalendarEvent = z.infer<typeof CalendarEventSchema>
export type CalendarFeed = z.infer<typeof CalendarFeedSchema>

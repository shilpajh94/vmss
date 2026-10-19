import z from "zod"
import { PaginationMetaSchema } from "./pagination-meta-schema"

// One persisted in-app notification (API `NotificationOut`). `data` is the
// push payload's `data` verbatim: `invitationId`, `trackingId`, `action`,
// `reason`, `assignedRoleId`/`assignedUserId` — all optional, since an
// older or non-invitation notification may carry none of them.
export const NotificationFeedItemSchema = z.object({
  id: z.string().min(1),
  title: z.string(),
  body: z.string(),
  data: z.record(z.string(), z.string()),
  createdAt: z.string().min(1),
  readAt: z.string().nullable(),
})

export type NotificationFeedItem = z.infer<typeof NotificationFeedItemSchema>

export const NotificationFeedPageResponseSchema = z.object({
  success: z.boolean(),
  message: z.string(),
  data: z.array(NotificationFeedItemSchema),
  pagination: PaginationMetaSchema,
})

export type NotificationFeedPage = {
  items: NotificationFeedItem[]
  total: number
}

export const NotificationUnreadCountResponseSchema = z.object({
  success: z.boolean(),
  message: z.string(),
  data: z.object({ unreadCount: z.number().int().nonnegative() }),
})

export const NotificationResponseSchema = z.object({
  success: z.boolean(),
  message: z.string(),
  data: NotificationFeedItemSchema,
})

export const MarkAllNotificationsReadResponseSchema = z.object({
  success: z.boolean(),
  message: z.string(),
  data: z.null(),
})

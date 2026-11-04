import z from 'zod'
import { PaginationMetaSchema } from './pagination-meta-schema'

// `eventType` stays a plain string on purpose: the API adds event types over
// time, and an enum here would fail the whole page on the first unknown one.
// Known values get a label via `KNOWN_TIMELINE_EVENT_TYPES`; the rest render
// as a generic event.
export const KNOWN_TIMELINE_EVENT_TYPES = [
  'invited',
  'approved',
  'denied',
  'approval_reverted',
  'id_verified',
  'photo_captured',
  'checked_in',
  'checked_out',
  'badge_printed',
  'badge_reprinted',
  'notification_sent',
  'zone_entered',
  'zone_exited',
  'zone_entry_denied',
] as const

export const VisitTimelineEventSchema = z.object({
  eventType: z.string(),
  occurredAt: z.string(),
  // Display-ready, contact details already masked — show verbatim.
  summary: z.string(),
  // null for system or visitor actions (QR check-in, auto check-out).
  actorName: z.string().nullish(),
})

export type VisitTimelineEvent = z.infer<typeof VisitTimelineEventSchema>

export const VisitTimelineResponseSchema = z.object({
  success: z.boolean(),
  message: z.string(),
  data: z.array(VisitTimelineEventSchema),
  pagination: PaginationMetaSchema,
})

export type VisitTimelineResponse = z.infer<typeof VisitTimelineResponseSchema>

export interface VisitTimelineQuery {
  page?: number
  pageSize?: number
  occurredAfter?: string
  occurredBefore?: string
  sortBy?: 'occurred_at' | 'event_type'
  sortOrder?: 'asc' | 'desc'
}

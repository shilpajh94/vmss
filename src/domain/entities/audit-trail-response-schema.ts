import z from "zod"
import { AuditLogEntrySchema } from "./audit-log-entry-schema"

export const AuditTrailStatsSchema = z.object({
  totalCheckIns: z.number(),
  deniedEntries: z.number(),
  overstayedVisits: z.number(),
})

export type AuditTrailStats = z.infer<typeof AuditTrailStatsSchema>

export const AuditTrailResponseSchema = z.object({
  items: z.array(AuditLogEntrySchema),
  total: z.number(),
  stats: AuditTrailStatsSchema,
})

export type AuditTrailResponse = z.infer<typeof AuditTrailResponseSchema>

import z from "zod"
import { AuditLogEntrySchema } from "./audit-log-entry-schema"
import { PaginationMetaSchema } from "./pagination-meta-schema"

export const AuditTrailResponseSchema = z.object({
  items: z.array(AuditLogEntrySchema),
  total: z.number(),
})

export type AuditTrailResponse = z.infer<typeof AuditTrailResponseSchema>

export const AuditTrailPaginatedResponseSchema = z.object({
  success: z.boolean(),
  message: z.string(),
  data: z.array(AuditLogEntrySchema),
  pagination: PaginationMetaSchema,
})

export type AuditTrailPaginatedResponse = z.infer<typeof AuditTrailPaginatedResponseSchema>

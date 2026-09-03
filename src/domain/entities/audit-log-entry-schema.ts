import z from "zod"

export const AuditLogEntrySchema = z.object({
  id: z.string().min(1),
  actorUserId: z.string().nullable(),
  action: z.string().min(1),
  entityType: z.string().min(1),
  entityId: z.string().nullable(),
  createdAt: z.string().min(1),
})

export type AuditLogEntry = z.infer<typeof AuditLogEntrySchema>

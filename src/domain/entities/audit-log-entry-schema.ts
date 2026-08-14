import z from "zod"

export const AuditLogEntrySchema = z.object({
  id: z.string().min(1),
  timestamp: z.string().min(1),
  activity: z.string().min(1),
  visitorName: z.string().min(1),
  description: z.string().min(1),
  zone: z.string().min(1),
  method: z.string().min(1),
  status: z.string().min(1),
})

export type AuditLogEntry = z.infer<typeof AuditLogEntrySchema>

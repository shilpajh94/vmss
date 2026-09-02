import z from "zod"

export const AuditReportJobSchema = z.object({
  id: z.string().min(1),
  status: z.string().min(1),
  formats: z.array(z.string()),
  requestedAt: z.string().min(1),
  completedAt: z.string().nullable(),
  errorMessage: z.string().nullable(),
  csvDownloadUrl: z.string().nullable(),
  pdfDownloadUrl: z.string().nullable(),
})

export type AuditReportJob = z.infer<typeof AuditReportJobSchema>

export const AuditReportJobResponseSchema = z.object({
  success: z.boolean(),
  message: z.string(),
  data: AuditReportJobSchema,
})

export type AuditReportJobResponse = z.infer<typeof AuditReportJobResponseSchema>

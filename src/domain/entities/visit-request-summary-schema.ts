import z from "zod"

export const VisitRequestSummarySchema = z.object({
  id: z.string().min(1),
  trackingId: z.string().min(1),
  primaryContactFullName: z.string().min(1),
  purposeOfVisit: z.string().min(1),
  registrationType: z.enum(["individual", "group"]),
  visitorCategoryId: z.string().nullable(),
  source: z.string().min(1),
  status: z.string().min(1),
  submittedAt: z.string().min(1),
  approvedAt: z.string().nullable(),
  expiresAt: z.string().min(1),
})

export type VisitRequestSummary = z.infer<typeof VisitRequestSummarySchema>

export const VisitRequestSummaryListResponseSchema = z.object({
  success: z.boolean(),
  message: z.string(),
  data: z.array(VisitRequestSummarySchema),
  pagination: z.object({
    page: z.number(),
    pageSize: z.number(),
    total: z.number(),
    totalPages: z.number(),
  }),
})

export type VisitRequestSummaryListResponse = z.infer<typeof VisitRequestSummaryListResponseSchema>

export const InvitationActionResultSchema = z.object({
  success: z.boolean(),
  message: z.string(),
})

export type InvitationActionResult = z.infer<typeof InvitationActionResultSchema>

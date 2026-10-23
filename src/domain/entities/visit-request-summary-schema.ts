import z from "zod"
import { PaginationMetaSchema } from "./pagination-meta-schema"
import { CurrentApprovalStepSchema } from "./invitation-detail-schema"

export const VisitRequestSummarySchema = z.object({
  id: z.string().min(1),
  trackingId: z.string().min(1),
  primaryContactFullName: z.string().min(1),
  purposeOfVisit: z.string().nullable(),
  registrationType: z.enum(["individual", "group"]),
  visitorCategoryId: z.string().nullable(),
  source: z.string().min(1),
  status: z.string().min(1),
  submittedAt: z.string().nullable(),
  approvedAt: z.string().nullable(),
  expiresAt: z.string().min(1),
  preferredVisitDate: z.string().nullish(),
  preferredVisitTime: z.string().nullish(),
  // Lets a board card show its approval level without a per-card detail
  // request (design D12). Absent from an API that predates it.
  currentApprovalStep: CurrentApprovalStepSchema.nullish(),
})

export type VisitRequestSummary = z.infer<typeof VisitRequestSummarySchema>

export const VisitRequestSummaryListResponseSchema = z.object({
  success: z.boolean(),
  message: z.string(),
  data: z.array(VisitRequestSummarySchema),
  pagination: PaginationMetaSchema,
})

export type VisitRequestSummaryListResponse = z.infer<typeof VisitRequestSummaryListResponseSchema>

export const InvitationActionResultSchema = z.object({
  success: z.boolean(),
  message: z.string(),
})

export type InvitationActionResult = z.infer<typeof InvitationActionResultSchema>

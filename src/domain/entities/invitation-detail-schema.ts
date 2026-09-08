import z from "zod"

export const CurrentApprovalStepSchema = z.object({
  id: z.string().min(1),
  stepOrder: z.number(),
  approverRoleId: z.string().nullable(),
  approverUserId: z.string().nullable(),
  totalSteps: z.number(),
  delegatedToUserId: z.string().nullable(),
})

export type CurrentApprovalStep = z.infer<typeof CurrentApprovalStepSchema>

// Wire shape of each `data.visitors[]` entry on GET /invitations/:id — the
// additional group visitors beyond the primary contact (who is instead
// flattened onto the invitation as `primaryContactFullName`, etc.).
export const InvitationVisitorSchema = z.object({
  id: z.string().min(1),
  fullName: z.string().min(1),
  email: z.string().nullable(),
  phone: z.string().nullable(),
  idProofType: z.string().nullable(),
  photoUrl: z.string().nullish(),
  idProofUrl: z.string().nullish(),
})

export type InvitationVisitor = z.infer<typeof InvitationVisitorSchema>

export const InvitationDetailSchema = z.object({
  id: z.string().min(1),
  branchId: z.string().nullable(),
  source: z.string().min(1),
  createdByUserId: z.string().nullable(),
  trackingId: z.string().min(1),
  status: z.string().min(1),
  registrationType: z.enum(["individual", "group"]),
  visitorCategoryId: z.string().nullable(),
  primaryContactFullName: z.string().min(1),
  primaryContactPhotoUrl: z.string().nullish(),
  primaryContactIdProofType: z.string().nullish(),
  primaryContactIdProofUrl: z.string().nullish(),
  purposeOfVisit: z.string().min(1),
  hostNameOrEmail: z.string().nullable(),
  hostId: z.string().nullable(),
  preferredVisitDate: z.string().nullish(),
  preferredVisitTime: z.string().nullish(),
  previousPreferredVisitDate: z.string().nullish(),
  previousPreferredVisitTime: z.string().nullish(),
  rescheduledAt: z.string().nullish(),
  rescheduleCount: z.number().default(0),
  expectedDuration: z.string().nullable(),
  departmentToVisit: z.string().nullable(),
  additionalNotes: z.string().nullable(),
  carriedItems: z.array(z.string()),
  carriedItemsDescription: z.string().nullable(),
  expiresAt: z.string().min(1),
  submittedAt: z.string().min(1),
  approvedAt: z.string().nullable(),
  currentApprovalStep: CurrentApprovalStepSchema.nullable(),
  denialReason: z.string().nullable(),
  deniedAt: z.string().nullable(),
  checkedInAt: z.string().nullable(),
  checkedInByUserId: z.string().nullable(),
  checkedOutAt: z.string().nullable(),
  checkedOutByUserId: z.string().nullable(),
  badgeNumber: z.string().nullable(),
  badgeIssuedAt: z.string().nullable(),
  badgeReprintCount: z.number(),
  watchlistFlagged: z.boolean(),
  watchlistOverrideAt: z.string().nullable(),
  watchlistOverrideReason: z.string().nullable(),
  watchlistOverrideByUserId: z.string().nullable(),
  visitors: z.array(InvitationVisitorSchema),
  vehicles: z.array(z.unknown()),
})

export type InvitationDetail = z.infer<typeof InvitationDetailSchema>

export const InvitationDetailResponseSchema = z.object({
  success: z.boolean(),
  message: z.string(),
  data: InvitationDetailSchema,
})

export type InvitationDetailResponse = z.infer<typeof InvitationDetailResponseSchema>

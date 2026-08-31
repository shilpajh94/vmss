import z from "zod"

export const CurrentApprovalStepSchema = z.object({
  id: z.string().min(1),
  stepOrder: z.number(),
  approverRoleId: z.string().nullable(),
  approverUserId: z.string().nullable(),
  totalSteps: z.number(),
})

export type CurrentApprovalStep = z.infer<typeof CurrentApprovalStepSchema>

export const InvitationDetailSchema = z.object({
  id: z.string().min(1),
  status: z.string().min(1),
  visitorCategoryId: z.string().nullable(),
  currentApprovalStep: CurrentApprovalStepSchema.nullable(),
})

export type InvitationDetail = z.infer<typeof InvitationDetailSchema>

export const InvitationDetailResponseSchema = z.object({
  success: z.boolean(),
  message: z.string(),
  data: InvitationDetailSchema,
})

export type InvitationDetailResponse = z.infer<typeof InvitationDetailResponseSchema>

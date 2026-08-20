import z from "zod"

export const InvitationTrackOutSchema = z.object({
  trackingId: z.string(),
  status: z.string(),
  preferredVisitDate: z.string().nullable().optional(),
  submittedAt: z.string().nullable().optional(),
  hostNameOrEmail: z.string().nullable().optional(),
  visitors: z.array(z.unknown()).optional(),
})

export type InvitationTrackOut = z.infer<typeof InvitationTrackOutSchema>

export const InvitationTrackResponseSchema = z.object({
  success: z.boolean(),
  message: z.string(),
  data: InvitationTrackOutSchema,
})

export type InvitationTrackResponse = z.infer<typeof InvitationTrackResponseSchema>

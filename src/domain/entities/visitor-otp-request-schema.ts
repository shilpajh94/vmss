import z from "zod"

export const OtpChannelSchema = z.enum(["email", "sms", "whatsapp"])
export type OtpChannel = z.infer<typeof OtpChannelSchema>

export const VisitorOtpRequestSchema = z.object({
  registrationType: z.enum(["individual", "group"]),
  contact: z.string().min(1),
})

export type VisitorOtpRequest = z.infer<typeof VisitorOtpRequestSchema>

export const VisitorOtpRequestResponseSchema = z.object({
  success: z.boolean(),
  message: z.string(),
  data: z.object({
    identifier: z.string(),
    channel: OtpChannelSchema,
  }),
})

export type VisitorOtpRequestResponse = z.infer<typeof VisitorOtpRequestResponseSchema>

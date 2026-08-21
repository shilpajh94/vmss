import z from "zod"
import { OtpChannelSchema } from "./visitor-otp-request-schema"

export const VisitorOtpVerifySchema = z.object({
  contact: z.string().min(1),
  code: z.string().min(1),
})

export type VisitorOtpVerify = z.infer<typeof VisitorOtpVerifySchema>

export const VisitorOtpVerifyResponseSchema = z.object({
  success: z.boolean(),
  message: z.string(),
  data: z.object({
    identifier: z.string(),
    channel: OtpChannelSchema,
    proofToken: z.string(),
  }),
})

export type VisitorOtpVerifyResponse = z.infer<typeof VisitorOtpVerifyResponseSchema>

import z from "zod"

export const VisitorOtpVerifySchema = z.object({
  contact: z.string().min(1),
  code: z.string().min(1),
})

export type VisitorOtpVerify = z.infer<typeof VisitorOtpVerifySchema>

export const VisitorOtpVerifyResponseSchema = z.object({
  verified: z.boolean(),
})

export type VisitorOtpVerifyResponse = z.infer<typeof VisitorOtpVerifyResponseSchema>

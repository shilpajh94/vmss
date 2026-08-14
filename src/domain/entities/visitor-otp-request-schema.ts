import z from "zod"

export const VisitorOtpRequestSchema = z.object({
  registrationType: z.enum(["individual", "group"]),
  contact: z.string().min(1),
})

export type VisitorOtpRequest = z.infer<typeof VisitorOtpRequestSchema>

export const VisitorOtpRequestResponseSchema = z.object({
  requested: z.boolean(),
})

export type VisitorOtpRequestResponse = z.infer<typeof VisitorOtpRequestResponseSchema>

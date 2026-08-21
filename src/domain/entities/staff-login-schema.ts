import z from "zod"

export const StaffLoginRequestSchema = z.object({
  email: z.string().email(),
  password: z.string(),
})

export type StaffLoginRequest = z.infer<typeof StaffLoginRequestSchema>

export const StaffLoginTokenSchema = z.object({
  accessToken: z.string(),
  refreshToken: z.string(),
  tokenType: z.string(),
})

export const StaffLoginResponseSchema = z.object({
  success: z.boolean(),
  message: z.string(),
  data: StaffLoginTokenSchema,
})

export type StaffLoginResponse = z.infer<typeof StaffLoginResponseSchema>

export const StaffLoginResultSchema = z.object({
  token: z.string(),
})

export type StaffLoginResult = z.infer<typeof StaffLoginResultSchema>

import z from "zod"

export const SsoExchangeRequestSchema = z.object({
  code: z.string(),
})

export type SsoExchangeRequest = z.infer<typeof SsoExchangeRequestSchema>

export const SsoTokenSchema = z.object({
  accessToken: z.string(),
  refreshToken: z.string(),
  tokenType: z.string(),
})

export const SsoExchangeResponseSchema = z.object({
  success: z.boolean(),
  message: z.string(),
  data: SsoTokenSchema,
})

export type SsoExchangeResponse = z.infer<typeof SsoExchangeResponseSchema>

export const SsoExchangeResultSchema = z.object({
  token: z.string(),
})

export type SsoExchangeResult = z.infer<typeof SsoExchangeResultSchema>

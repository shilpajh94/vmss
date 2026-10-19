import z from "zod"

export const KioskLocationValidationSchema = z.object({
  enforceKioskLocationValidation: z.boolean(),
})

export type KioskLocationValidation = z.infer<typeof KioskLocationValidationSchema>

export const KioskLocationValidationResponseSchema = z.object({
  success: z.boolean(),
  message: z.string(),
  data: KioskLocationValidationSchema,
})

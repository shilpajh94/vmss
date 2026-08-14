import z from "zod"

export const StaffSsoInitiateResponseSchema = z.object({
  redirectUrl: z.string(),
})

export type StaffSsoInitiateResponse = z.infer<typeof StaffSsoInitiateResponseSchema>

import z from "zod"

export const HostSearchResultOutSchema = z.object({
  id: z.string(),
  name: z.string(),
  email: z.string(),
  department: z.string().nullable(),
})

export type HostSearchResultOut = z.infer<typeof HostSearchResultOutSchema>

export const HostSearchEnvelopeSchema = z.object({
  success: z.boolean(),
  message: z.string(),
  data: z.object({
    hosts: z.array(HostSearchResultOutSchema),
  }),
})

export type HostSearchEnvelope = z.infer<typeof HostSearchEnvelopeSchema>

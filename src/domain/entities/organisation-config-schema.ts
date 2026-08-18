import z from "zod"

export const OrganisationConfigSchema = z.object({
  organisationName: z.string().min(1),
  logoUrl: z.string().optional(),
  defaultTimezone: z.string().min(1),
  autoApprovePreRegistered: z.boolean(),
  passBadgeExpiryDuration: z.string().min(1),
})

export type OrganisationConfig = z.infer<typeof OrganisationConfigSchema>

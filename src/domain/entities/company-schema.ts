import z from "zod"

export const CompanySchema = z.object({
  id: z.string(),
  legalName: z.string(),
  registrationNumber: z.string().nullable(),
  taxId: z.string().nullable(),
  email: z.string().nullable(),
  phone: z.string().nullable(),
  address: z.string().nullable(),
  logoUrl: z.string().nullable(),
  isActive: z.boolean(),
  defaultTimezone: z.string().nullable(),
  autoApprovePreRegisteredVisitors: z.boolean(),
  badgeExpiryDurationMinutes: z.number().nullable(),
})

export type Company = z.infer<typeof CompanySchema>

export const CompanyResponseSchema = z.object({
  success: z.boolean(),
  message: z.string(),
  data: CompanySchema,
})

export type CompanyResponse = z.infer<typeof CompanyResponseSchema>

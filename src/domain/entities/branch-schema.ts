import z from "zod"

export const BranchSchema = z.object({
  id: z.string().min(1),
  name: z.string().min(1),
  code: z.string().min(1),
  city: z.string(),
  country: z.string(),
  address: z.string(),
  contactPersonUserId: z.string(),
  contactEmail: z.string(),
  contactPhone: z.string(),
  operatingHoursFrom: z.string().optional(),
  operatingHoursTo: z.string().optional(),
  notes: z.string().optional(),
  isActive: z.boolean(),
})

export type Branch = z.infer<typeof BranchSchema>

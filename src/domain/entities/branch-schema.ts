import z from "zod"

export const BranchSchema = z.object({
  id: z.string().min(1),
  name: z.string().min(1),
  locationCity: z.string().min(1),
  branchCode: z.string().min(1),
  contactPerson: z.string().min(1),
  country: z.string().min(1),
  physicalAddress: z.string().min(1),
  contactEmail: z.string().min(1),
  contactPhone: z.string().min(1),
  operatingHoursFrom: z.string().optional(),
  operatingHoursTo: z.string().optional(),
  notes: z.string().optional(),
  status: z.enum(["active", "inactive"]),
})

export type Branch = z.infer<typeof BranchSchema>

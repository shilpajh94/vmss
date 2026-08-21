import z from "zod"

export const BranchOutSchema = z.object({
  id: z.string(),
  name: z.string(),
  code: z.string(),
  address: z.string().nullable(),
  isActive: z.boolean(),
  city: z.string().nullable(),
  country: z.string().nullable(),
  contactPersonUserId: z.string().nullable(),
  contactEmail: z.string().nullable(),
  contactPhone: z.string().nullable(),
  operatingHoursFrom: z.string().nullable(),
  operatingHoursTo: z.string().nullable(),
  notes: z.string().nullable(),
})

export type BranchOut = z.infer<typeof BranchOutSchema>

export const BranchResponseSchema = z.object({
  success: z.boolean(),
  message: z.string(),
  data: BranchOutSchema,
})

export type BranchResponse = z.infer<typeof BranchResponseSchema>

export const BranchListResponseSchema = z.object({
  success: z.boolean(),
  message: z.string(),
  data: z.array(BranchOutSchema),
  pagination: z.object({
    page: z.number(),
    pageSize: z.number(),
    total: z.number(),
    totalPages: z.number(),
  }),
})

export type BranchListResponse = z.infer<typeof BranchListResponseSchema>

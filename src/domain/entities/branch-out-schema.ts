import z from "zod"
import { PaginationMetaSchema } from "./pagination-meta-schema"

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
  pagination: PaginationMetaSchema,
})

export type BranchListResponse = z.infer<typeof BranchListResponseSchema>

import z from "zod"
import { PaginationMetaSchema } from "./pagination-meta-schema"

export const KioskSchema = z.object({
  id: z.string(),
  name: z.string(),
  description: z.string().nullish(),
  isActive: z.boolean(),
  isHidden: z.boolean().default(false),
})

export type Kiosk = z.infer<typeof KioskSchema>

export interface KioskInput {
  name: string
  description?: string
  isActive: boolean
}

export const KioskResponseSchema = z.object({
  success: z.boolean(),
  message: z.string(),
  data: KioskSchema,
})

export type KioskResponse = z.infer<typeof KioskResponseSchema>

export const KioskListResponseSchema = z.object({
  success: z.boolean(),
  message: z.string(),
  data: z.array(KioskSchema),
  pagination: PaginationMetaSchema,
})

export type KioskListResponse = z.infer<typeof KioskListResponseSchema>

import z from "zod"
import { PaginationMetaSchema } from "./pagination-meta-schema"

// Wire contract for `/zones` (camelCase). Zones carry their linked `gateIds`
// so the guard app can resolve its gate and zone from `GET /zones`.
export const ZoneSchema = z.object({
  id: z.string(),
  branchId: z.string(),
  name: z.string(),
  code: z.string(),
  buildingId: z.string().nullish(),
  floorId: z.string().nullish(),
  gateIds: z.array(z.string()).nullish().transform((ids) => ids ?? []),
  isActive: z.boolean().default(true),
  // The branch's default zone is always allowed for every visitor. Absent on a backend that predates it.
  isDefault: z.boolean().default(false),
})

export type Zone = z.infer<typeof ZoneSchema>

export const ZoneResponseSchema = z.object({
  success: z.boolean(),
  message: z.string(),
  data: ZoneSchema,
})

export const ZoneListResponseSchema = z.object({
  success: z.boolean(),
  message: z.string(),
  data: z.array(ZoneSchema),
  pagination: PaginationMetaSchema,
})

export type ZoneListResponse = z.infer<typeof ZoneListResponseSchema>

// A mapping endpoint answers with the mapped zones; accept either a bare list
// (of zone objects or ids) or an object holding `zoneIds`/`zones`, and reduce
// it to the ids the UI works with.
const ZoneRefSchema = z.union([z.string(), z.object({ id: z.string() }).transform((zone) => zone.id), z.object({ zoneId: z.string() }).transform((zone) => zone.zoneId)])
const ZoneIdsSchema = z.union([
  z.array(ZoneRefSchema),
  z.object({ zoneIds: z.array(ZoneRefSchema) }).transform((value) => value.zoneIds),
  z.object({ zones: z.array(ZoneRefSchema) }).transform((value) => value.zones),
])

export const ZoneIdsResponseSchema = z
  .object({ success: z.boolean(), message: z.string(), data: ZoneIdsSchema })
  .transform((response) => response.data)

/** Body of `POST /zones`; `PUT /zones/{id}` takes the same minus `branchId`. */
export interface ZoneInput {
  branchId: string
  name: string
  code: string
  buildingId?: string | null
  floorId?: string | null
  gateIds: string[]
  isActive?: boolean
  isDefault?: boolean
}

export type ZoneSortBy = "name" | "created_at"

import z from "zod"
import { PaginationMetaSchema } from "./pagination-meta-schema"

// Tenant fields the badge print flow cares about. `badgePrintFlowEnabled` is
// absent on a backend that predates the flow, so it defaults to off.
export const TenantMeResponseSchema = z.object({
  success: z.boolean().optional(),
  data: z.object({
    badgePrintFlowEnabled: z.boolean().optional().default(false),
    // Absent on a backend without zone access control, so it defaults to off.
    zoneAccessEnabled: z.boolean().optional().default(false),
  }),
})

export const TenantSettingsResponseSchema = z.object({
  success: z.boolean().optional(),
  data: z.object({ badgePrintFlowEnabled: z.boolean().optional(), zoneAccessEnabled: z.boolean().optional() }).optional(),
})

export const CheckinSearchRowSchema = z.object({
  id: z.string().min(1),
  trackingId: z.string(),
  fullName: z.string(),
  phone: z.string().nullable().optional(),
  status: z.string(),
  checkInStatus: z.string().nullable().optional(),
  hasPhoto: z.boolean(),
  idVerifiedAt: z.string().nullable().optional(),
  hasActiveBadge: z.boolean(),
})

export type CheckinSearchRow = z.infer<typeof CheckinSearchRowSchema>

export const CheckinSearchResponseSchema = z.object({
  success: z.boolean().optional(),
  data: z.array(CheckinSearchRowSchema),
  pagination: PaginationMetaSchema,
})

export const CheckinPhotoResponseSchema = z.object({
  success: z.boolean().optional(),
  data: CheckinSearchRowSchema,
})

export type CheckinSearchPage = { items: CheckinSearchRow[]; total: number }

// The verify-id body isn't part of the contract: any 2xx means verified.
export const CheckinVerifyIdResponseSchema = z.unknown()

export const BadgeScanResultSchema = z.object({
  id: z.string(),
  trackingId: z.string(),
  status: z.string(),
  checkInStatus: z.string().nullable().optional(),
})

export type BadgeScanResult = z.infer<typeof BadgeScanResultSchema>

// The envelope is the usual `{ success, data }`, but the scan routes are
// documented as returning the object itself, so accept either.
export const BadgeScanResponseSchema = z
  .union([z.object({ data: BadgeScanResultSchema }).transform((value) => value.data), BadgeScanResultSchema])
  .pipe(BadgeScanResultSchema)

// ASSUMED contract (not yet confirmed by the backend): print/reprint return the
// badge data as JSON so the frontend can render the ID card. `token` is the
// signed credential the scan page accepts; it is encoded in the QR only.
export const BadgeCardSchema = z.object({
  token: z.string().min(1),
  visitorName: z.string(),
  purpose: z.string().nullable().optional(),
  hostName: z.string().nullable().optional(),
  photoUrl: z.string().nullable().optional(),
})

export type BadgeCard = z.infer<typeof BadgeCardSchema>

export const BadgeCardResponseSchema = z
  .union([z.object({ data: BadgeCardSchema }).transform((value) => value.data), BadgeCardSchema])
  .pipe(BadgeCardSchema)

// Until the backend ships badge JSON, print/reprint still answer with a PDF.
export type BadgeOutput = { kind: 'card'; card: BadgeCard } | { kind: 'pdf'; blob: Blob }

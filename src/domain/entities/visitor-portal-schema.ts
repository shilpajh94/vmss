import z from "zod"

// Wire shape of `GET /visitor-portal/me`'s `data`
// (vmss_api/visitor_return_visit/schemas.py::ReturningVisitorLookupOut).
export const VisitHistoryEntrySchema = z.object({
  trackingId: z.string().min(1),
  status: z.string().min(1),
  visitDate: z.string().nullable(),
  purpose: z.string().nullable(),
})

export type VisitHistoryEntry = z.infer<typeof VisitHistoryEntrySchema>

// Drawn from the visitor's most recent prior visit. `idProofUrl`/`photoUrl`
// are presigned, time-limited URLs the wizard offers to reuse (see
// allow-returning-visitor-photo-id-reuse) rather than always requiring a
// fresh upload.
export const VisitorPrefillSchema = z.object({
  fullName: z.string().min(1),
  email: z.string().nullable(),
  phone: z.string().nullable(),
  preferredContactMethod: z.string().min(1),
  idProofType: z.string().nullable(),
  idProofUrl: z.string().nullish(),
  photoUrl: z.string().nullish(),
  visitorCategoryId: z.string().nullable(),
})

export type VisitorPrefill = z.infer<typeof VisitorPrefillSchema>

export const VisitorPortalPaginationSchema = z.object({
  page: z.number(),
  pageSize: z.number(),
  total: z.number(),
  totalPages: z.number(),
})

export type VisitorPortalPagination = z.infer<typeof VisitorPortalPaginationSchema>

export const VisitorPortalMeSchema = z.object({
  history: z.array(VisitHistoryEntrySchema),
  prefill: VisitorPrefillSchema.nullable(),
  pagination: VisitorPortalPaginationSchema,
})

export type VisitorPortalMe = z.infer<typeof VisitorPortalMeSchema>

export const VisitorPortalMeResponseSchema = z.object({
  success: z.boolean(),
  message: z.string(),
  data: VisitorPortalMeSchema,
})

export type VisitorPortalMeResponse = z.infer<typeof VisitorPortalMeResponseSchema>

import z from "zod"

// Wire shape of `GET /invitations/lookup-by-email`'s `data` — the most
// recently known profile for a visitor identified by email, used by staff
// registration to prefill the Primary Contact fields. `data` is null when
// no visitor matches that email (not an error). `idProofUrl`/`photoUrl` are
// signed, time-limited URLs to the visitor's prior ID-proof document/photo
// (see visitor-portal-schema.ts's matching fields) — reused rather than
// always requiring a fresh upload.
export const StaffVisitorLookupSchema = z.object({
  fullName: z.string().min(1),
  phone: z.string().nullable(),
  preferredContactMethod: z.enum(["email", "sms"]).nullable(),
  visitorCategoryId: z.string().nullable(),
  idProofType: z.string().nullable(),
  idProofUrl: z.string().nullish(),
  photoUrl: z.string().nullish(),
})

export type StaffVisitorLookup = z.infer<typeof StaffVisitorLookupSchema>

export const StaffVisitorLookupResponseSchema = z.object({
  success: z.boolean(),
  message: z.string(),
  data: StaffVisitorLookupSchema.nullable(),
})

export type StaffVisitorLookupResponse = z.infer<typeof StaffVisitorLookupResponseSchema>

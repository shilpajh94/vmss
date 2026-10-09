import z from "zod"

// Wire shape for `payload.primaryContact` and each `payload.visitors[]` entry on
// POST /registrations/walk-in. ID-proof images travel as separate multipart file
// fields (matched by order for `visitors`), never inline here. Neither carries
// its own `customFields` — every Visitor Info answer, for the primary contact
// or any additional visitor, flows through the request's single top-level
// `customFields` array instead (restructure-walkin-payload-by-field-id).
export const VisitorSchema = z
  .object({
    fullName: z.string().min(1),
    email: z.string().email().optional(),
    phone: z.string().min(1).optional(),
    preferredContactMethod: z.enum(["email", "sms"]).optional(),
    // Branch-configurable (form-builder) — not every branch requires or
    // even shows ID Proof Type, so it's omitted rather than sent empty.
    idProofType: z.string().min(1).optional(),
  })
  .refine((visitor) => Boolean(visitor.email || visitor.phone), {
    message: "Either email or phone is required.",
    path: ["email"],
  })

export type Visitor = z.infer<typeof VisitorSchema>

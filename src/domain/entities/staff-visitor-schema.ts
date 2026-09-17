import z from "zod"

// Wire shape for `payload.primaryContact` and each `payload.visitors[]` entry on
// POST /invitations — identical contract to POST /registrations/walk-in (see
// visitor-schema.ts). ID-proof images travel as separate multipart file fields.
export const StaffVisitorSchema = z
  .object({
    fullName: z.string().min(1),
    email: z.string().email().optional(),
    phone: z.string().min(1).optional(),
    preferredContactMethod: z.enum(["email", "sms"]).optional(),
    idProofType: z.string().min(1),
    // See visitor-schema.ts's matching comment.
    customFieldValues: z.record(z.string(), z.unknown()).optional(),
  })
  .refine((visitor) => Boolean(visitor.email || visitor.phone), {
    message: "Either email or phone is required.",
    path: ["email"],
  })

export type StaffVisitor = z.infer<typeof StaffVisitorSchema>

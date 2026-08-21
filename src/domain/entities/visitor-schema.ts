import z from "zod"

// Wire shape for `payload.primaryContact` and each `payload.visitors[]` entry on
// POST /registrations/walk-in. ID-proof images travel as separate multipart file
// fields (matched by order for `visitors`), never inline here.
export const VisitorSchema = z
  .object({
    fullName: z.string().min(1),
    email: z.string().email().optional(),
    phone: z.string().min(1).optional(),
    preferredContactMethod: z.enum(["email", "sms"]).optional(),
    idProofType: z.string().min(1),
  })
  .refine((visitor) => Boolean(visitor.email || visitor.phone), {
    message: "Either email or phone is required.",
    path: ["email"],
  })

export type Visitor = z.infer<typeof VisitorSchema>

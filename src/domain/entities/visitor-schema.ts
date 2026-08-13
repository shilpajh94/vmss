import z from "zod"

export const VisitorSchema = z.object({
  fullName: z.string().min(1),
  email: z.string().email(),
  phone: z.string().min(1),
  address: z.string().min(1),
  visitorCategory: z.string().min(1),
  // Only the primary contact fills this in; additional group visitors leave it unset.
  preferredContactMethod: z.enum(["email", "sms"]).optional(),
  idProofType: z.string().min(1),
  idProofFileRef: z.string().optional(),
  profileImageFileRef: z.string().optional(),
})

export type Visitor = z.infer<typeof VisitorSchema>

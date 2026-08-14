import z from "zod"

export const StaffVisitorSchema = z.object({
  fullName: z.string().min(1),
  email: z.string().email(),
  phone: z.string().min(1),
  preferredContactMethod: z.enum(["email", "sms"]).optional(),
  idProofType: z.string().min(1),
  idProofFileRef: z.string().optional(),
})

export type StaffVisitor = z.infer<typeof StaffVisitorSchema>

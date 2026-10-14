import z from "zod"

// Delivery channel for visitor notifications; only one is used per visitor.
export const PreferredContactMethodSchema = z.enum(["email", "sms", "whatsapp"])

export type PreferredContactMethod = z.infer<typeof PreferredContactMethodSchema>

export const PREFERRED_CONTACT_METHOD_LABELS: Record<PreferredContactMethod, string> = {
  email: "Email",
  sms: "SMS",
  whatsapp: "WhatsApp",
}

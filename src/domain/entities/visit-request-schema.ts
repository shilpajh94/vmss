import z from "zod"
import { VehicleSchema } from "./vehicle-schema"
import { VisitorSchema } from "./visitor-schema"

// Wire shape of the JSON-encoded `payload` field for
// POST /registrations/walk-in (identical contract to POST /invitations).
export const VisitRequestSchema = z.object({
  registrationType: z.enum(["individual", "group"]),
  visitorCategoryId: z.string().min(1),
  primaryContact: VisitorSchema,
  visitors: z.array(VisitorSchema),
  visitDetails: z.object({
    purposeOfVisit: z.string().min(1),
    hostNameOrEmail: z.string().min(1),
    preferredVisitDate: z.string().min(1),
    preferredVisitTime: z.string().min(1),
    expectedDuration: z.string().min(1),
    departmentToVisit: z.string().min(1),
    additionalNotes: z.string().optional(),
  }),
  carriedItems: z.object({
    items: z.array(z.string()),
    itemDescription: z.string().optional(),
  }),
  vehicles: z.array(VehicleSchema),
  consents: z.object({
    termsAccepted: z.boolean(),
    dataProcessingAccepted: z.boolean(),
    safetyGuidelinesAccepted: z.boolean(),
  }),
})

export type VisitRequest = z.infer<typeof VisitRequestSchema>

export const VisitRequestResponseSchema = z.object({
  trackingId: z.string().min(1),
  status: z.string().min(1),
  submittedAt: z.string().min(1),
})

export type VisitRequestResponse = z.infer<typeof VisitRequestResponseSchema>

// `InvitationOut`, wrapped in the standard `Envelope[...]` response shape.
export const InvitationOutSchema = z.object({
  id: z.string().min(1),
  trackingId: z.string().min(1),
  registrationType: z.enum(["individual", "group"]),
  source: z.string().min(1),
  status: z.string().min(1),
  expiresAt: z.string().min(1),
  submittedAt: z.string().min(1).nullable(),
})

export const InvitationEnvelopeSchema = z.object({
  success: z.boolean(),
  message: z.string(),
  data: InvitationOutSchema,
})

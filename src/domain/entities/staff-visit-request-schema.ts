import z from "zod"
import { VehicleSchema } from "./vehicle-schema"
import { StaffVisitorSchema } from "./staff-visitor-schema"
import { ConsentAnswerSchema, FieldAnswerSchema, GroupAnswerSchema } from "./form-field-answer-schema"

// Wire shape of the JSON-encoded `payload` field for POST /invitations
// (identical contract to POST /registrations/walk-in, see visit-request-schema.ts).
// `visitDetails.branchId` is sent in the payload (not an `X-Branch-ID` header, which prod's CORS rejects).
// `hostId`/`hostNameOrEmail`/`departmentToVisit` are intentionally absent
// (role-based-invitation-workflow) — see visit-request-schema.ts's comment.
export const StaffVisitRequestSchema = z.object({
  registrationType: z.enum(["individual", "group"]),
  visitorCategoryId: z.string().min(1),
  primaryContact: StaffVisitorSchema,
  // See visit-request-schema.ts's matching comment — safe to omit when empty.
  visitors: z.array(StaffVisitorSchema).optional(),
  visitDetails: z.object({
    branchId: z.string().min(1),
    buildingId: z.string().min(1).optional(),
    purposeOfVisit: z.string().min(1),
    preferredVisitDate: z.string().min(1),
    preferredVisitTime: z.string().min(1),
  }),
  // See visit-request-schema.ts's matching comment — safe to omit when empty.
  carriedItems: z
    .object({
      items: z.array(z.string()),
      itemDescription: z.string().optional(),
    })
    .optional(),
  // See visit-request-schema.ts's matching comment.
  vehicles: z.array(VehicleSchema).optional(),
  // Addressed by fieldId — see visit-request-schema.ts's matching comment.
  // NOTE: omitting this when empty is expected to fail backend validation.
  consents: z.array(ConsentAnswerSchema).optional(),
  // See visit-request-schema.ts's matching comment.
  customFields: z.array(FieldAnswerSchema).optional(),
  // See visit-request-schema.ts's matching comment.
  groups: z.array(GroupAnswerSchema).optional(),
})

export type StaffVisitRequest = z.infer<typeof StaffVisitRequestSchema>

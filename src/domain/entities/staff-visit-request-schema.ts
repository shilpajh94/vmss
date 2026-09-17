import z from "zod"
import { VehicleSchema } from "./vehicle-schema"
import { StaffVisitorSchema } from "./staff-visitor-schema"

// Wire shape of the JSON-encoded `payload` field for POST /invitations
// (identical contract to POST /registrations/walk-in, see visit-request-schema.ts).
// `branchId` isn't part of this payload — it travels as the `X-Branch-ID` header.
// `hostId`/`hostNameOrEmail`/`departmentToVisit` are intentionally absent
// (role-based-invitation-workflow) — see visit-request-schema.ts's comment.
export const StaffVisitRequestSchema = z.object({
  registrationType: z.enum(["individual", "group"]),
  visitorCategoryId: z.string().min(1),
  primaryContact: StaffVisitorSchema,
  visitors: z.array(StaffVisitorSchema),
  visitDetails: z.object({
    purposeOfVisit: z.string().min(1),
    preferredVisitDate: z.string().min(1),
    preferredVisitTime: z.string().min(1),
    expectedDuration: z.string().min(1),
    additionalNotes: z.string().optional(),
  }),
  carriedItems: z.object({
    items: z.array(z.string()),
    itemDescription: z.string().optional(),
  }),
  vehicles: z.array(VehicleSchema),
  // Dynamic, branch-configured keys (form-builder) — see
  // visit-request-schema.ts's matching comment.
  consents: z.record(z.string(), z.boolean()),
  // See visit-request-schema.ts's matching comment.
  customFieldValues: z.record(z.string(), z.unknown()).optional(),
})

export type StaffVisitRequest = z.infer<typeof StaffVisitRequestSchema>

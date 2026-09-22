import z from "zod"
import { VehicleSchema } from "./vehicle-schema"
import { VisitorSchema } from "./visitor-schema"

// Wire shape of the JSON-encoded `payload` field for
// POST /registrations/walk-in (identical contract to POST /invitations).
// `hostId`/`hostNameOrEmail`/`departmentToVisit` are intentionally absent
// (role-based-invitation-workflow) — the API accepts them as optional but
// the wizard no longer collects or sends any of the three.
export const VisitRequestSchema = z.object({
  registrationType: z.enum(["individual", "group"]),
  visitorCategoryId: z.string().min(1),
  primaryContact: VisitorSchema,
  visitors: z.array(VisitorSchema),
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
  // Dynamic, branch-configured keys (form-builder) — never camelCased,
  // since they're admin-defined data, not a fixed schema field name. See
  // `VMSS_API/docs/features/invitations.md`'s "Branch-configurable
  // requiredness" section.
  consents: z.record(z.string(), z.boolean()),
  // Answers for admin-authored fields on Visit Details, Carried Items
  // (beyond its own `items` field), or a custom step
  // (add-generic-custom-field-support) — Consent Agreement's fields
  // (system or admin-authored) continue to flow through `consents` above
  // instead, unaffected by this field.
  customFieldValues: z.record(z.string(), z.unknown()).optional(),
  // Per-instance answers for a custom (admin-defined) repeatable field group
  // (add-repeatable-field-groups) — keyed by the group's own `key`, an
  // ordered array of that group's per-instance answer maps, each keyed by
  // the group's field keys. The two built-in repeatable groups ("vehicles"/
  // "visitors") keep submitting through their own dedicated `vehicles`/
  // `visitors` fields above instead — this is only for a group an admin
  // defines beyond those two.
  groupValues: z.record(z.string(), z.array(z.record(z.string(), z.unknown()))).optional(),
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

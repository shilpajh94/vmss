import z from "zod"
import { VehicleSchema } from "./vehicle-schema"
import { VisitorSchema } from "./visitor-schema"
import { ConsentAnswerSchema, FieldAnswerSchema, GroupAnswerSchema } from "./form-field-answer-schema"

// Wire shape of the JSON-encoded `payload` field for
// POST /registrations/walk-in (identical contract to POST /invitations).
// `hostId`/`hostNameOrEmail`/`departmentToVisit` are intentionally absent
// (role-based-invitation-workflow) — the API accepts them as optional but
// the wizard no longer collects or sends any of the three.
export const VisitRequestSchema = z.object({
  registrationType: z.enum(["individual", "group"]),
  visitorCategoryId: z.string().min(1),
  primaryContact: VisitorSchema,
  // Backend default (`Field(default_factory=list)`) — safe to omit entirely
  // when empty rather than send `[]`.
  visitors: z.array(VisitorSchema).optional(),
  visitDetails: z.object({
    purposeOfVisit: z.string().min(1),
    preferredVisitDate: z.string().min(1),
    preferredVisitTime: z.string().min(1),
  }),
  // Backend default (`Field(default_factory=CarriedItemsSubmit)`, itself
  // `items: []`/`itemDescription: None`) — safe to omit entirely when both
  // are empty, same as `visitors`/`vehicles` below.
  carriedItems: z
    .object({
      items: z.array(z.string()),
      itemDescription: z.string().optional(),
    })
    .optional(),
  // See `visitors`' matching comment.
  vehicles: z.array(VehicleSchema).optional(),
  // One entry per active Consent Agreement field, addressed by fieldId
  // (restructure-walkin-payload-by-field-id) — never a hardcoded key, since
  // these are branch-configured (form-builder). Backend now defaults this
  // to `[]` when omitted, same as `visitors`/`vehicles`/`carriedItems`/
  // `customFields`/`groups` above; a branch's *required* consent fields are
  // still enforced separately and will 422 if not submitted as accepted.
  consents: z.array(ConsentAnswerSchema).optional(),
  // Answers for admin-authored fields on Visit Details, Carried Items
  // (beyond its own `items` field), or a custom step
  // (add-generic-custom-field-support) — Consent Agreement's fields
  // (system or admin-authored) continue to flow through `consents` above
  // instead, unaffected by this field.
  customFields: z.array(FieldAnswerSchema).optional(),
  // Per-instance answers for a custom (admin-defined) repeatable field group
  // (add-repeatable-field-groups), addressed by groupId/fieldId. The two
  // built-in repeatable groups ("vehicles"/"visitors") keep submitting
  // through their own dedicated `vehicles`/`visitors` fields above instead —
  // this is only for a group an admin defines beyond those two.
  groups: z.array(GroupAnswerSchema).optional(),
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

import z from "zod"
import { DeviceSummarySchema } from "./managed-device-schema"
import { FieldAnswerSchema, GroupAnswerSchema } from "./form-field-answer-schema"

export const CurrentApprovalStepSchema = z.object({
  id: z.string().min(1),
  stepOrder: z.number(),
  approverRoleId: z.string().nullable(),
  approverUserId: z.string().nullable(),
  totalSteps: z.number(),
  delegatedToUserId: z.string().nullable(),
})

export type CurrentApprovalStep = z.infer<typeof CurrentApprovalStepSchema>

// Wire shape of each `data.visitors[]` entry on GET /invitations/:id — the
// additional group visitors beyond the primary contact (who is instead
// flattened onto the invitation as `primaryContactFullName`, etc.).
export const InvitationVisitorSchema = z.object({
  id: z.string().min(1),
  fullName: z.string().min(1),
  email: z.string().nullable(),
  phone: z.string().nullable(),
  idProofType: z.string().nullable(),
  photoUrl: z.string().nullish(),
  idProofUrl: z.string().nullish(),
  // fieldId-addressed, same wire shape as the submission-side `customFields`
  // (`InvitationVisitorDetailOut.custom_fields: list[CustomFieldValue]`) —
  // NOT a flat key-based map. Backend resolves `file_upload` answers here to
  // signed URLs the same way it does for `customFields`/
  // `primaryContactCustomFields`, gated by the caller's `documents:view`
  // grant (InvitationVisitorDetailOut).
  customFields: z.array(FieldAnswerSchema).default([]),
})

export type InvitationVisitor = z.infer<typeof InvitationVisitorSchema>

// Wire shape of each `data.vehicles[]` entry on GET /invitations/:id —
// fields kept `.nullish()` since the exact response shape for this array
// (submitted via `VehicleSchema` at POST time) hasn't been confirmed yet.
export const InvitationVehicleSchema = z.object({
  id: z.string().nullish(),
  vehicleType: z.string().nullish(),
  licensePlate: z.string().nullish(),
  makeModel: z.string().nullish(),
  color: z.string().nullish(),
  // fieldId-addressed, same wire shape as `InvitationVisitorSchema.customFields`
  // (`InvitationVehicleOut.custom_fields: list[CustomFieldValue]`). NOTE:
  // unlike visitors/primary-contact/invitation/group scopes, the backend
  // does not yet resolve `file_upload` answers here to signed URLs — a
  // file_upload field's value may still be an opaque storage key.
  // VisitorInfoModal's FileValueField already falls back to a plain "File
  // uploaded" indicator for non-URL values, so this is safe to render now;
  // revisit once the backend adds resolution for vehicles too.
  customFields: z.array(FieldAnswerSchema).default([]),
})

export type InvitationVehicle = z.infer<typeof InvitationVehicleSchema>

export const InvitationDetailSchema = z.object({
  id: z.string().min(1),
  branchId: z.string().nullable(),
  source: z.string().min(1),
  createdByUserId: z.string().nullable(),
  trackingId: z.string().min(1),
  status: z.string().min(1),
  registrationType: z.enum(["individual", "group"]),
  visitorCategoryId: z.string().nullable(),
  primaryContactFullName: z.string().min(1),
  primaryContactEmail: z.string().nullish(),
  primaryContactPhone: z.string().nullish(),
  primaryContactPhotoUrl: z.string().nullish(),
  primaryContactIdProofType: z.string().nullish(),
  primaryContactIdProofUrl: z.string().nullish(),
  // Admin-configured (form-builder) field answers — fieldId/groupId-addressed,
  // matching `InvitationDetailOut`'s `primary_contact_custom_fields`/
  // `custom_fields`/`groups` (VMSS_API `invitations/schemas.py`), the same
  // wire shape the submission side uses (`VisitRequestSchema`'s
  // `customFields`/`groups`). Rendered generically in VisitorInfoModal via
  // `findFieldById`/`findGroupById` rather than typed field-by-field, since
  // the field set varies per branch/publish.
  primaryContactCustomFields: z.array(FieldAnswerSchema).default([]),
  customFields: z.array(FieldAnswerSchema).default([]),
  groups: z.array(GroupAnswerSchema).default([]),
  purposeOfVisit: z.string().min(1),
  hostNameOrEmail: z.string().nullable(),
  hostId: z.string().nullable(),
  pocUserId: z.string().nullable(),
  pocRoleId: z.string().nullable(),
  pocName: z.string().nullable(),
  preferredVisitDate: z.string().nullish(),
  preferredVisitTime: z.string().nullish(),
  previousPreferredVisitDate: z.string().nullish(),
  previousPreferredVisitTime: z.string().nullish(),
  rescheduledAt: z.string().nullish(),
  rescheduleCount: z.number().default(0),
  expectedDuration: z.string().nullable(),
  departmentToVisit: z.string().nullable(),
  additionalNotes: z.string().nullable(),
  carriedItems: z.array(z.string()),
  carriedItemsDescription: z.string().nullable(),
  expiresAt: z.string().min(1),
  submittedAt: z.string().min(1),
  approvedAt: z.string().nullable(),
  currentApprovalStep: CurrentApprovalStepSchema.nullable(),
  denialReason: z.string().nullable(),
  deniedAt: z.string().nullable(),
  checkedInAt: z.string().nullable(),
  checkedInByUserId: z.string().nullable(),
  checkedOutAt: z.string().nullable(),
  checkedOutByUserId: z.string().nullable(),
  checkInDevice: DeviceSummarySchema.nullish(),
  checkOutDevice: DeviceSummarySchema.nullish(),
  badgeNumber: z.string().nullable(),
  badgeIssuedAt: z.string().nullable(),
  badgeReprintCount: z.number(),
  watchlistFlagged: z.boolean(),
  watchlistOverrideAt: z.string().nullable(),
  watchlistOverrideReason: z.string().nullable(),
  watchlistOverrideByUserId: z.string().nullable(),
  visitors: z.array(InvitationVisitorSchema),
  vehicles: z.array(InvitationVehicleSchema),
})

export type InvitationDetail = z.infer<typeof InvitationDetailSchema>

export const InvitationDetailResponseSchema = z.object({
  success: z.boolean(),
  message: z.string(),
  data: InvitationDetailSchema,
})

export type InvitationDetailResponse = z.infer<typeof InvitationDetailResponseSchema>

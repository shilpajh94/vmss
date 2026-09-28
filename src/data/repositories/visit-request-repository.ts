import type { VisitRequest, VisitRequestResponse } from '../../domain/entities/visit-request-schema'

// Shared by both invitation-creating flows (staff pre-registration and visitor
// walk-in) — each ID-proof travels as a raw multipart file, not a pre-uploaded ref.
export interface InvitationSubmissionFiles {
  // Optional: branch-configured (form-builder) — the calling branch may
  // have deactivated ID proof and/or profile photo for Visitor Info, in
  // which case the caller omits the file entirely rather than sending an
  // empty part (specs/invitations/spec.md "ID proof not required when the
  // branch has deactivated it" / "Missing primary contact photo is accepted
  // when the branch has deactivated it").
  primaryContactIdProofFile: File | undefined
  primaryContactPhotoFile: File | undefined
  visitorIdProofFiles: File[]
  // Order-matched to `additionalVisitors`, same convention as
  // `visitorIdProofFiles` — currently always empty, since no wizard UI
  // collects a profile photo for anyone but the primary contact, but still
  // wired through for contract completeness.
  visitorPhotoFiles: File[]
  // Admin-defined field groups' own `file_upload` field answers
  // (add-group-field-file-upload), keyed by the group's `id` — each
  // value is that group's file list, order-matched to
  // `payload.groups[<groupId>].instances`. Built by
  // `extractGroupFieldFiles`, which also strips the field from the
  // `groups` JSON (the backend rejects it if both are present).
  groupFieldFiles: Record<string, File[]>
  // Admin-authored `file_upload` fields added directly on a step (not
  // inside a repeatable group) — backend's "inline file-upload custom
  // fields" contract (2026-09-24). Each bucket is keyed by the field's own
  // `id`; the field's answer must be entirely absent from
  // `customFields`/`groups` JSON (a 422 if both are present). Built by
  // `custom-field-files.ts`'s extraction helpers.
  primaryContactCustomFieldFiles: Record<string, File>
  visitorCustomFieldFiles: Record<string, File[]>
  vehicleCustomFieldFiles: Record<string, File[]>
  customFieldFiles: Record<string, File>
}

export interface VisitRequestRepository {
  submit(request: VisitRequest, files: InvitationSubmissionFiles): Promise<VisitRequestResponse>
}

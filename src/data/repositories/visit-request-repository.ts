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
  // Admin-defined field groups' own `file_upload` field answers
  // (add-group-field-file-upload), keyed by the group's `key` — each
  // value is that group's file list, order-matched to
  // `payload.groupValues[<groupKey>]` instances. Built by
  // `extractGroupFieldFiles`, which also strips the field from `payload`'s
  // `groupValues` JSON (the backend rejects it if both are present).
  groupFieldFiles: Record<string, File[]>
}

export interface VisitRequestRepository {
  submit(request: VisitRequest, files: InvitationSubmissionFiles): Promise<VisitRequestResponse>
}

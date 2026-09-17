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
}

export interface VisitRequestRepository {
  submit(request: VisitRequest, files: InvitationSubmissionFiles): Promise<VisitRequestResponse>
}

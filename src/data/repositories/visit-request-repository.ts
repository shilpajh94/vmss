import type { VisitRequest, VisitRequestResponse } from '../../domain/entities/visit-request-schema'

// Shared by both invitation-creating flows (staff pre-registration and visitor
// walk-in) — each ID-proof travels as a raw multipart file, not a pre-uploaded ref.
export interface InvitationSubmissionFiles {
  primaryContactIdProofFile: File
  visitorIdProofFiles: File[]
}

export interface VisitRequestRepository {
  submit(request: VisitRequest, files: InvitationSubmissionFiles): Promise<VisitRequestResponse>
}

import type { StaffVisitRequest } from '../../domain/entities/staff-visit-request-schema'
import type { VisitRequestResponse } from '../../domain/entities/visit-request-schema'
import type { InvitationSubmissionFiles } from './visit-request-repository'

export interface StaffVisitRequestRepository {
  // POST /invitations needs "X-Branch-ID header or branchId in payload" — sent
  // as `request.visitDetails.branchId` (the header is CORS-blocked on prod).
  submit(request: StaffVisitRequest, files: InvitationSubmissionFiles): Promise<VisitRequestResponse>
}

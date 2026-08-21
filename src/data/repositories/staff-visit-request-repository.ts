import type { StaffVisitRequest } from '../../domain/entities/staff-visit-request-schema'
import type { VisitRequestResponse } from '../../domain/entities/visit-request-schema'
import type { InvitationSubmissionFiles } from './visit-request-repository'

export interface StaffVisitRequestRepository {
  // `branchId` satisfies POST /invitations' "X-Branch-ID header or branchId in
  // payload, one of the two is required" rule — sent as the header here.
  submit(request: StaffVisitRequest, files: InvitationSubmissionFiles, branchId: string): Promise<VisitRequestResponse>
}

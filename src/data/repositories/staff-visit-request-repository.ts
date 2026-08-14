import type { StaffVisitRequest } from '../../domain/entities/staff-visit-request-schema'
import type { VisitRequestResponse } from '../../domain/entities/visit-request-schema'

export interface StaffVisitRequestRepository {
  submit(request: StaffVisitRequest): Promise<VisitRequestResponse>
}

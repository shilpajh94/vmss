import type { StaffVisitRequestRepository } from '../repositories/staff-visit-request-repository'
import type { StaffVisitRequest } from '../../domain/entities/staff-visit-request-schema'
import type { VisitRequestResponse } from '../../domain/entities/visit-request-schema'

export class SubmitStaffVisitRequestUseCase {
  private readonly staffVisitRequestRepository: StaffVisitRequestRepository

  constructor(staffVisitRequestRepository: StaffVisitRequestRepository) {
    this.staffVisitRequestRepository = staffVisitRequestRepository
  }

  async execute(request: StaffVisitRequest): Promise<VisitRequestResponse> {
    return this.staffVisitRequestRepository.submit(request)
  }
}

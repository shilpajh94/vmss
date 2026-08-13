import type { VisitRequestRepository } from '../repositories/visit-request-repository'
import type { VisitRequest, VisitRequestResponse } from '../../domain/entities/visit-request-schema'

export class SubmitVisitRequestUseCase {
  private readonly visitRequestRepository: VisitRequestRepository

  constructor(visitRequestRepository: VisitRequestRepository) {
    this.visitRequestRepository = visitRequestRepository
  }

  async execute(request: VisitRequest): Promise<VisitRequestResponse> {
    return this.visitRequestRepository.submit(request)
  }
}

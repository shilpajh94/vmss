import type { VisitRequestSummaryRepository } from '../repositories/visit-request-summary-repository'

export class ApproveInvitationUseCase {
  private readonly visitRequestSummaryRepository: VisitRequestSummaryRepository

  constructor(visitRequestSummaryRepository: VisitRequestSummaryRepository) {
    this.visitRequestSummaryRepository = visitRequestSummaryRepository
  }

  async execute(id: string): Promise<void> {
    return this.visitRequestSummaryRepository.approve(id)
  }
}

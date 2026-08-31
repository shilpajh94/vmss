import type { VisitRequestSummaryRepository } from '../repositories/visit-request-summary-repository'

export class DenyInvitationUseCase {
  private readonly visitRequestSummaryRepository: VisitRequestSummaryRepository

  constructor(visitRequestSummaryRepository: VisitRequestSummaryRepository) {
    this.visitRequestSummaryRepository = visitRequestSummaryRepository
  }

  async execute(id: string, reason: string): Promise<void> {
    return this.visitRequestSummaryRepository.deny(id, reason)
  }
}

import type { VisitRequestSummaryRepository } from '../repositories/visit-request-summary-repository'

export class CheckOutInvitationUseCase {
  private readonly visitRequestSummaryRepository: VisitRequestSummaryRepository

  constructor(visitRequestSummaryRepository: VisitRequestSummaryRepository) {
    this.visitRequestSummaryRepository = visitRequestSummaryRepository
  }

  async execute(id: string, idempotencyKey: string): Promise<void> {
    return this.visitRequestSummaryRepository.checkOut(id, idempotencyKey)
  }
}

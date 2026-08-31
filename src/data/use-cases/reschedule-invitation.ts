import type { VisitRequestSummaryRepository } from '../repositories/visit-request-summary-repository'

export class RescheduleInvitationUseCase {
  private readonly visitRequestSummaryRepository: VisitRequestSummaryRepository

  constructor(visitRequestSummaryRepository: VisitRequestSummaryRepository) {
    this.visitRequestSummaryRepository = visitRequestSummaryRepository
  }

  async execute(id: string, preferredVisitDate: string, preferredVisitTime: string): Promise<void> {
    return this.visitRequestSummaryRepository.reschedule(id, preferredVisitDate, preferredVisitTime)
  }
}

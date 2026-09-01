import type { VisitRequestSummaryRepository } from '../repositories/visit-request-summary-repository'

export class RejectInvitationStepUseCase {
  private readonly visitRequestSummaryRepository: VisitRequestSummaryRepository

  constructor(visitRequestSummaryRepository: VisitRequestSummaryRepository) {
    this.visitRequestSummaryRepository = visitRequestSummaryRepository
  }

  async execute(invitationId: string, stepId: string, reason: string): Promise<void> {
    return this.visitRequestSummaryRepository.rejectStep(invitationId, stepId, reason)
  }
}

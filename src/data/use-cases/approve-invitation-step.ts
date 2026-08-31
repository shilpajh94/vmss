import type { VisitRequestSummaryRepository } from '../repositories/visit-request-summary-repository'

export class ApproveInvitationStepUseCase {
  private readonly visitRequestSummaryRepository: VisitRequestSummaryRepository

  constructor(visitRequestSummaryRepository: VisitRequestSummaryRepository) {
    this.visitRequestSummaryRepository = visitRequestSummaryRepository
  }

  async execute(invitationId: string, stepId: string): Promise<void> {
    return this.visitRequestSummaryRepository.approveStep(invitationId, stepId)
  }
}

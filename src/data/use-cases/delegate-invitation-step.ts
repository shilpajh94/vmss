import type { VisitRequestSummaryRepository } from '../repositories/visit-request-summary-repository'

export class DelegateInvitationStepUseCase {
  private readonly visitRequestSummaryRepository: VisitRequestSummaryRepository

  constructor(visitRequestSummaryRepository: VisitRequestSummaryRepository) {
    this.visitRequestSummaryRepository = visitRequestSummaryRepository
  }

  async execute(invitationId: string, stepId: string, delegateUserId: string): Promise<void> {
    return this.visitRequestSummaryRepository.delegateStep(invitationId, stepId, delegateUserId)
  }
}

import type { VisitRequestSummaryRepository } from '../repositories/visit-request-summary-repository'
import type { InvitationDetail } from '../../domain/entities/invitation-detail-schema'

export class GetInvitationDetailUseCase {
  private readonly visitRequestSummaryRepository: VisitRequestSummaryRepository

  constructor(visitRequestSummaryRepository: VisitRequestSummaryRepository) {
    this.visitRequestSummaryRepository = visitRequestSummaryRepository
  }

  async execute(id: string): Promise<InvitationDetail> {
    return this.visitRequestSummaryRepository.getDetail(id)
  }
}

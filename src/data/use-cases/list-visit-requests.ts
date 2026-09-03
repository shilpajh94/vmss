import type { VisitRequestSummaryRepository } from '../repositories/visit-request-summary-repository'
import type { VisitRequestSummary } from '../../domain/entities/visit-request-summary-schema'

export class ListVisitRequestsUseCase {
  private readonly visitRequestSummaryRepository: VisitRequestSummaryRepository

  constructor(visitRequestSummaryRepository: VisitRequestSummaryRepository) {
    this.visitRequestSummaryRepository = visitRequestSummaryRepository
  }

  async execute(relevantToMe?: boolean): Promise<VisitRequestSummary[]> {
    return this.visitRequestSummaryRepository.list({ relevantToMe })
  }
}

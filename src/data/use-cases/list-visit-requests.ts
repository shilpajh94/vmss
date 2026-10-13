import type { ListVisitRequestsParams, VisitRequestSummaryRepository, VisitRequestsPage } from '../repositories/visit-request-summary-repository'

export class ListVisitRequestsUseCase {
  private readonly visitRequestSummaryRepository: VisitRequestSummaryRepository

  constructor(visitRequestSummaryRepository: VisitRequestSummaryRepository) {
    this.visitRequestSummaryRepository = visitRequestSummaryRepository
  }

  async execute(params?: ListVisitRequestsParams): Promise<VisitRequestsPage> {
    return this.visitRequestSummaryRepository.list(params)
  }
}

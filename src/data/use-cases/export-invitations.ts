import type { InvitationExportParams, VisitRequestSummaryRepository } from '../repositories/visit-request-summary-repository'

export class ExportInvitationsUseCase {
  private readonly visitRequestSummaryRepository: VisitRequestSummaryRepository

  constructor(visitRequestSummaryRepository: VisitRequestSummaryRepository) {
    this.visitRequestSummaryRepository = visitRequestSummaryRepository
  }

  async execute(params: InvitationExportParams): Promise<Blob> {
    return this.visitRequestSummaryRepository.export(params)
  }
}

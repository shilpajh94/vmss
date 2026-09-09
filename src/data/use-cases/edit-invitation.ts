import type { EditInvitationFields, VisitRequestSummaryRepository } from '../repositories/visit-request-summary-repository'

export class EditInvitationUseCase {
  private readonly visitRequestSummaryRepository: VisitRequestSummaryRepository

  constructor(visitRequestSummaryRepository: VisitRequestSummaryRepository) {
    this.visitRequestSummaryRepository = visitRequestSummaryRepository
  }

  async execute(id: string, fields: EditInvitationFields): Promise<void> {
    return this.visitRequestSummaryRepository.edit(id, fields)
  }
}

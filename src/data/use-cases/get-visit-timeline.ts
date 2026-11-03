import type { VisitTimelineQuery, VisitTimelineResponse } from '../../domain/entities/visit-timeline-schema'
import type { VisitTimelineRepository } from '../repositories/visit-timeline-repository'

export class GetVisitTimelineUseCase {
  private readonly visitTimelineRepository: VisitTimelineRepository

  constructor(visitTimelineRepository: VisitTimelineRepository) {
    this.visitTimelineRepository = visitTimelineRepository
  }

  async execute(invitationId: string, query?: VisitTimelineQuery): Promise<VisitTimelineResponse> {
    return this.visitTimelineRepository.listForInvitation(invitationId, query)
  }

  async executeForVisitor(visitorId: string, query?: VisitTimelineQuery): Promise<VisitTimelineResponse> {
    return this.visitTimelineRepository.listForVisitor(visitorId, query)
  }
}

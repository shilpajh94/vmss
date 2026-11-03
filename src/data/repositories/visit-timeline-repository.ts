import type { VisitTimelineQuery, VisitTimelineResponse } from '../../domain/entities/visit-timeline-schema'

export interface VisitTimelineRepository {
  // The whole visit; the only option for an individual invitation, whose
  // primary contact has no visitor id.
  listForInvitation(invitationId: string, query?: VisitTimelineQuery): Promise<VisitTimelineResponse>
  // A co-visitor of a group invitation; returns that visit's timeline.
  listForVisitor(visitorId: string, query?: VisitTimelineQuery): Promise<VisitTimelineResponse>
}

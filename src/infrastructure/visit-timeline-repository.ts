import { API_ENDPOINTS } from '../data/api/api-endpoints'
import type { ApiClient } from '../data/api/api-client'
import type { VisitTimelineRepository } from '../data/repositories/visit-timeline-repository'
import { VisitTimelineResponseSchema, type VisitTimelineQuery, type VisitTimelineResponse } from '../domain/entities/visit-timeline-schema'

export class HttpVisitTimelineRepository implements VisitTimelineRepository {
  private readonly apiClient: ApiClient

  constructor(apiClient: ApiClient) {
    this.apiClient = apiClient
  }

  listForInvitation(invitationId: string, query?: VisitTimelineQuery): Promise<VisitTimelineResponse> {
    return this.apiClient.makeRequest({
      endpointConfig: API_ENDPOINTS.GET_INVITATION_TIMELINE,
      pathParams: { invitationId },
      queryParams: { ...query },
      parserSchema: VisitTimelineResponseSchema,
    })
  }

  listForVisitor(visitorId: string, query?: VisitTimelineQuery): Promise<VisitTimelineResponse> {
    return this.apiClient.makeRequest({
      endpointConfig: API_ENDPOINTS.GET_VISITOR_TIMELINE,
      pathParams: { visitorId },
      queryParams: { ...query },
      parserSchema: VisitTimelineResponseSchema,
    })
  }
}

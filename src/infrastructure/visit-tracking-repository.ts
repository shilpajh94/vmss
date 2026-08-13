import { API_ENDPOINTS } from '../data/api/api-endpoints'
import type { ApiClient } from '../data/api/api-client'
import type { VisitTrackingRepository } from '../data/repositories/visit-tracking-repository'
import { TrackingLookupResponseSchema, type TrackingLookupResponse } from '../domain/entities/tracking-lookup-response-schema'

export class HttpVisitTrackingRepository implements VisitTrackingRepository {
  private readonly apiClient: ApiClient

  constructor(apiClient: ApiClient) {
    this.apiClient = apiClient
  }

  async lookup(trackingId: string): Promise<TrackingLookupResponse> {
    return this.apiClient.makeRequest<TrackingLookupResponse>({
      endpointConfig: API_ENDPOINTS.TRACK_VISIT_REQUEST,
      queryParams: { trackingId },
      parserSchema: TrackingLookupResponseSchema,
    })
  }
}

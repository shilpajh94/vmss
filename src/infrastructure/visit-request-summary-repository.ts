import { API_ENDPOINTS } from '../data/api/api-endpoints'
import type { ApiClient } from '../data/api/api-client'
import type { VisitRequestSummaryRepository } from '../data/repositories/visit-request-summary-repository'
import {
  VisitRequestSummaryListResponseSchema,
  type VisitRequestSummary,
  type VisitRequestSummaryListResponse,
} from '../domain/entities/visit-request-summary-schema'

export class HttpVisitRequestSummaryRepository implements VisitRequestSummaryRepository {
  private readonly apiClient: ApiClient

  constructor(apiClient: ApiClient) {
    this.apiClient = apiClient
  }

  async list(): Promise<VisitRequestSummary[]> {
    const response = await this.apiClient.makeRequest<VisitRequestSummaryListResponse>({
      endpointConfig: API_ENDPOINTS.LIST_VISIT_REQUESTS,
      parserSchema: VisitRequestSummaryListResponseSchema,
    })

    return response.data
  }
}

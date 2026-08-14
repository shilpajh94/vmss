import z from 'zod'
import { API_ENDPOINTS } from '../data/api/api-endpoints'
import type { ApiClient } from '../data/api/api-client'
import type { VisitRequestSummaryRepository } from '../data/repositories/visit-request-summary-repository'
import { VisitRequestSummarySchema, type VisitRequestSummary } from '../domain/entities/visit-request-summary-schema'

const VisitRequestSummaryListSchema = z.array(VisitRequestSummarySchema)

export class HttpVisitRequestSummaryRepository implements VisitRequestSummaryRepository {
  private readonly apiClient: ApiClient

  constructor(apiClient: ApiClient) {
    this.apiClient = apiClient
  }

  async list(): Promise<VisitRequestSummary[]> {
    return this.apiClient.makeRequest<VisitRequestSummary[]>({
      endpointConfig: API_ENDPOINTS.LIST_VISIT_REQUESTS,
      parserSchema: VisitRequestSummaryListSchema,
    })
  }
}

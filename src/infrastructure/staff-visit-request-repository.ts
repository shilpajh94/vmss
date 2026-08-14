import { API_ENDPOINTS } from '../data/api/api-endpoints'
import type { ApiClient } from '../data/api/api-client'
import type { StaffVisitRequestRepository } from '../data/repositories/staff-visit-request-repository'
import type { StaffVisitRequest } from '../domain/entities/staff-visit-request-schema'
import { VisitRequestResponseSchema, type VisitRequestResponse } from '../domain/entities/visit-request-schema'

export class HttpStaffVisitRequestRepository implements StaffVisitRequestRepository {
  private readonly apiClient: ApiClient

  constructor(apiClient: ApiClient) {
    this.apiClient = apiClient
  }

  async submit(request: StaffVisitRequest): Promise<VisitRequestResponse> {
    return this.apiClient.makeRequest<VisitRequestResponse>({
      endpointConfig: API_ENDPOINTS.STAFF_CREATE_VISIT_REQUEST,
      body: request,
      parserSchema: VisitRequestResponseSchema,
    })
  }
}

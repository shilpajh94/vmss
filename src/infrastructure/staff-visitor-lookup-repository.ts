import { API_ENDPOINTS } from '../data/api/api-endpoints'
import type { ApiClient } from '../data/api/api-client'
import type { StaffVisitorLookupRepository } from '../data/repositories/staff-visitor-lookup-repository'
import { StaffVisitorLookupResponseSchema, type StaffVisitorLookup } from '../domain/entities/staff-visitor-lookup-schema'

export class HttpStaffVisitorLookupRepository implements StaffVisitorLookupRepository {
  private readonly apiClient: ApiClient

  constructor(apiClient: ApiClient) {
    this.apiClient = apiClient
  }

  async lookupByEmail(email: string): Promise<StaffVisitorLookup | null> {
    const response = await this.apiClient.makeRequest({
      endpointConfig: API_ENDPOINTS.LOOKUP_STAFF_VISITOR_BY_EMAIL,
      queryParams: { email },
      parserSchema: StaffVisitorLookupResponseSchema,
    })

    return response.data
  }

  async lookupByPhone(phone: string): Promise<StaffVisitorLookup | null> {
    const response = await this.apiClient.makeRequest({
      endpointConfig: API_ENDPOINTS.LOOKUP_STAFF_VISITOR_BY_PHONE,
      queryParams: { phone },
      parserSchema: StaffVisitorLookupResponseSchema,
    })

    return response.data
  }
}

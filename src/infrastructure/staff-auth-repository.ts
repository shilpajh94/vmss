import { API_ENDPOINTS } from '../data/api/api-endpoints'
import type { ApiClient } from '../data/api/api-client'
import type { StaffAuthRepository } from '../data/repositories/staff-auth-repository'
import { StaffSsoInitiateResponseSchema, type StaffSsoInitiateResponse } from '../domain/entities/staff-sso-initiate-schema'

export class HttpStaffAuthRepository implements StaffAuthRepository {
  private readonly apiClient: ApiClient

  constructor(apiClient: ApiClient) {
    this.apiClient = apiClient
  }

  async initiateSso(): Promise<StaffSsoInitiateResponse> {
    return this.apiClient.makeRequest<StaffSsoInitiateResponse>({
      endpointConfig: API_ENDPOINTS.INITIATE_STAFF_SSO,
      parserSchema: StaffSsoInitiateResponseSchema,
    })
  }
}

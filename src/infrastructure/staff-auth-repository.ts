import { API_ENDPOINTS } from '../data/api/api-endpoints'
import type { ApiClient } from '../data/api/api-client'
import type { StaffAuthRepository } from '../data/repositories/staff-auth-repository'
import { StaffSsoInitiateResponseSchema, type StaffSsoInitiateResponse } from '../domain/entities/staff-sso-initiate-schema'
import { UserOutResponseSchema } from '../domain/entities/user-out-schema'
import type { StaffUser } from '../domain/entities/staff-user-schema'

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

  async getCurrentUser(): Promise<StaffUser> {
    const response = await this.apiClient.makeRequest({
      endpointConfig: API_ENDPOINTS.GET_CURRENT_STAFF_USER,
      parserSchema: UserOutResponseSchema,
    })

    return {
      name: response.data.fullName,
      role: response.data.branchRoles[0]?.roleName ?? 'Staff',
      isAdmin: response.data.branchRoles.some((branchRole) => branchRole.roleName.toLowerCase() === 'admin'),
    }
  }
}

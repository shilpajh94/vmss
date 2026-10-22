import { API_ENDPOINTS } from '../data/api/api-endpoints'
import type { ApiClient } from '../data/api/api-client'
import type { StaffAuthRepository } from '../data/repositories/staff-auth-repository'
import { StaffLoginResponseSchema, type StaffLoginResponse, type StaffLoginResult } from '../domain/entities/staff-login-schema'
import { UserOutResponseSchema } from '../domain/entities/user-out-schema'
import type { StaffUser } from '../domain/entities/staff-user-schema'

export class HttpStaffAuthRepository implements StaffAuthRepository {
  private readonly apiClient: ApiClient

  constructor(apiClient: ApiClient) {
    this.apiClient = apiClient
  }

  async login(email: string, password: string): Promise<StaffLoginResult> {
    const response = await this.apiClient.makeRequest<StaffLoginResponse>({
      endpointConfig: API_ENDPOINTS.STAFF_LOGIN,
      body: { email, password },
      parserSchema: StaffLoginResponseSchema,
    })

    return { token: response.data.accessToken }
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
      isReception: response.data.branchRoles.some((branchRole) => branchRole.roleName.toLowerCase() === 'reception'),
      branchRoles: response.data.branchRoles.map(({ roleName, branchId }) => ({ roleName, branchId })),
    }
  }
}

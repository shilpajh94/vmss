import { API_ENDPOINTS } from '../data/api/api-endpoints'
import type { ApiClient } from '../data/api/api-client'
import type { StaffAuthRepository } from '../data/repositories/staff-auth-repository'
import { StaffLoginResponseSchema, type StaffLoginResponse, type StaffLoginResult } from '../domain/entities/staff-login-schema'
import z from 'zod'
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

  async logout(): Promise<void> {
    await this.apiClient.makeRequest({ endpointConfig: API_ENDPOINTS.STAFF_LOGOUT, parserSchema: z.unknown() })
  }

  async getCurrentUser(): Promise<StaffUser> {
    const response = await this.apiClient.makeRequest({
      endpointConfig: API_ENDPOINTS.GET_CURRENT_STAFF_USER,
      parserSchema: UserOutResponseSchema,
    })

    // `isAdmin`/`isReception` only choose the landing page and the staff
    // sidebar, which the spec defines by role. What a user may *do* comes
    // from the permission codes (`presentation/utils/permissions.ts`).
    return {
      name: response.data.fullName,
      roles: response.data.branchRoles.length > 0 ? [...new Set(response.data.branchRoles.map((branchRole) => branchRole.roleName))] : ['Staff'],
      isAdmin: response.data.branchRoles.some((branchRole) => branchRole.roleName.toLowerCase() === 'admin'),
      isReception: response.data.branchRoles.some((branchRole) => branchRole.roleName.toLowerCase() === 'reception'),
      branchRoles: response.data.branchRoles.map(({ roleName, branchId, permissionCodes }) => ({ roleName, branchId, permissionCodes })),
    }
  }
}

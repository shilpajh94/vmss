import z from 'zod'
import { API_ENDPOINTS } from '../data/api/api-endpoints'
import type { ApiClient } from '../data/api/api-client'
import type { HostEmployeeRepository } from '../data/repositories/host-employee-repository'
import { EmployeeListResponseSchema, type EmployeeOut } from '../domain/entities/employee-out-schema'
import type { BranchRoleAssignment, HostEmployee, HostEmployeeCreateInput } from '../domain/entities/host-employee-schema'
import { RoleListResponseSchema, type RoleOut } from '../domain/entities/role-out-schema'
import { BranchRoleResponseSchema, UserOutResponseSchema } from '../domain/entities/user-out-schema'

function toHostEmployee(employee: EmployeeOut): HostEmployee {
  return {
    id: employee.id,
    fullName: employee.fullName,
    email: employee.email,
    employeeCode: employee.employeeCode ?? undefined,
    phoneNumber: employee.phoneNumber ?? undefined,
    designation: employee.designation ?? undefined,
    departmentId: employee.departmentId ?? undefined,
    isActive: employee.isActive,
    avatarUrl: employee.avatarUrl ?? undefined,
    branchRoles: employee.branchRoles.map((role) => ({ id: role.id, roleName: role.roleName, branchId: role.branchId ?? undefined })),
  }
}

export class HttpHostEmployeeRepository implements HostEmployeeRepository {
  private readonly apiClient: ApiClient

  constructor(apiClient: ApiClient) {
    this.apiClient = apiClient
  }

  async list(): Promise<HostEmployee[]> {
    const response = await this.apiClient.makeRequest({
      endpointConfig: API_ENDPOINTS.LIST_HOST_EMPLOYEES,
      queryParams: { pageSize: 100 },
      parserSchema: EmployeeListResponseSchema,
    })

    return response.data.map(toHostEmployee)
  }

  async create(input: HostEmployeeCreateInput): Promise<HostEmployee> {
    const response = await this.apiClient.makeRequest({
      endpointConfig: API_ENDPOINTS.CREATE_HOST_EMPLOYEE,
      body: { email: input.email, password: input.password, fullName: input.fullName },
      parserSchema: UserOutResponseSchema,
    })

    const user = response.data
    let branchRoles: BranchRoleAssignment[] = user.branchRoles.map((role) => ({
      id: role.id,
      roleName: role.roleName,
      branchId: role.branchId ?? undefined,
    }))

    if (input.roleId) {
      const assigned = await this.assignRole(user.id, input.roleId, input.branchId)
      branchRoles = [...branchRoles, assigned]
    }

    return {
      id: user.id,
      fullName: user.fullName,
      email: user.email,
      employeeCode: undefined,
      phoneNumber: undefined,
      designation: undefined,
      departmentId: undefined,
      isActive: user.isActive,
      avatarUrl: undefined,
      branchRoles,
    }
  }

  async listRoles(): Promise<RoleOut[]> {
    const response = await this.apiClient.makeRequest({
      endpointConfig: API_ENDPOINTS.LIST_ROLES,
      queryParams: { pageSize: 100 },
      parserSchema: RoleListResponseSchema,
    })

    return response.data
  }

  async assignRole(userId: string, roleId: string, branchId?: string): Promise<BranchRoleAssignment> {
    const response = await this.apiClient.makeRequest({
      endpointConfig: API_ENDPOINTS.ASSIGN_HOST_EMPLOYEE_ROLE,
      pathParams: { userId },
      body: { roleId, branchId: branchId ?? null },
      parserSchema: BranchRoleResponseSchema,
    })

    return { id: response.data.id, roleName: response.data.roleName, branchId: response.data.branchId ?? undefined }
  }

  async revokeRole(userId: string, assignmentId: string): Promise<void> {
    await this.apiClient.makeRequest<unknown>({
      endpointConfig: API_ENDPOINTS.REVOKE_HOST_EMPLOYEE_ROLE,
      pathParams: { userId, assignmentId },
      parserSchema: z.unknown(),
    })
  }
}

import z from 'zod'
import { API_ENDPOINTS } from '../data/api/api-endpoints'
import type { ApiClient } from '../data/api/api-client'
import type { HostEmployeeRepository } from '../data/repositories/host-employee-repository'
import { EmployeeListResponseSchema, type EmployeeOut } from '../domain/entities/employee-out-schema'
import { EmployeeSyncResponseSchema, type EmployeeSyncItem } from '../domain/entities/employee-sync-schema'
import type { BranchRoleAssignment, HostEmployee, HostEmployeeCreateInput } from '../domain/entities/host-employee-schema'
import { RoleListResponseSchema, type RoleOut } from '../domain/entities/role-out-schema'
import { BranchRoleResponseSchema } from '../domain/entities/user-out-schema'

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

  // The backend has no per-employee create endpoint — the employee directory
  // (what `list()` reads) is populated only via a company-wide sync that
  // replaces the whole roster. To add one employee without deactivating
  // everyone else, we re-send the full current roster plus the new entry.
  async create(input: HostEmployeeCreateInput): Promise<HostEmployee> {
    const existing = await this.list()

    const existingItems: EmployeeSyncItem[] = existing.map((employee) => ({
      email: employee.email,
      fullName: employee.fullName,
      employeeCode: employee.employeeCode ?? '',
      phoneNumber: employee.phoneNumber ?? null,
      designation: employee.designation ?? null,
      departmentId: employee.departmentId ?? null,
    }))

    const newItem: EmployeeSyncItem = {
      email: input.email,
      fullName: input.fullName,
      employeeCode: input.employeeCode,
      phoneNumber: input.phoneNumber ?? null,
      designation: input.designation ?? null,
      departmentId: input.departmentId ?? null,
    }

    await this.apiClient.makeRequest({
      endpointConfig: API_ENDPOINTS.SYNC_EMPLOYEES,
      body: { employees: [...existingItems, newItem] },
      parserSchema: EmployeeSyncResponseSchema,
    })

    const refreshed = await this.list()
    const created = refreshed.find((employee) => employee.email === input.email)
    if (!created) {
      throw new Error('Employee directory sync completed but the new employee could not be found afterward.')
    }

    if (input.roleId) {
      const assigned = await this.assignRole(created.id, input.roleId, input.branchId)
      return { ...created, branchRoles: [...created.branchRoles, assigned] }
    }

    return created
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

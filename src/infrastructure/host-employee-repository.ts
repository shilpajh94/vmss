import z from 'zod'
import { API_ENDPOINTS } from '../data/api/api-endpoints'
import type { ApiClient } from '../data/api/api-client'
import type {
  HostEmployeeRepository,
  HostEmployeesPage,
  ListHostEmployeesPageParams,
  ListRolesPageParams,
  RolesPage,
} from '../data/repositories/host-employee-repository'
import { EmployeeListResponseSchema, EmployeeResponseSchema, type EmployeeOut } from '../domain/entities/employee-out-schema'
import type { BranchRoleAssignment, HostEmployee, HostEmployeeCreateInput } from '../domain/entities/host-employee-schema'
import { RoleListResponseSchema, RoleResponseSchema, type RoleCreateInput, type RoleOut } from '../domain/entities/role-out-schema'
import {
  PermissionListResponseSchema,
  RolePermissionResyncResponseSchema,
  type PermissionOut,
  type RolePermissionResyncEntry,
} from '../domain/entities/permission-out-schema'
import { BranchRoleResponseSchema } from '../domain/entities/user-out-schema'
import { fetchAllPages } from '../data/api/fetch-all-pages'

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
    const employees = await fetchAllPages((page, pageSize) =>
      this.apiClient.makeRequest({
        endpointConfig: API_ENDPOINTS.LIST_HOST_EMPLOYEES,
        queryParams: { page, pageSize },
        parserSchema: EmployeeListResponseSchema,
      }),
    )

    return employees.map(toHostEmployee)
  }

  async listPage({ page, pageSize, departmentId, role, status }: ListHostEmployeesPageParams): Promise<HostEmployeesPage> {
    const response = await this.apiClient.makeRequest({
      endpointConfig: API_ENDPOINTS.LIST_HOST_EMPLOYEES,
      queryParams: { page, pageSize, departmentId, role, status },
      parserSchema: EmployeeListResponseSchema,
    })

    return { items: response.data.map(toHostEmployee), total: response.pagination.total }
  }

  async create(input: HostEmployeeCreateInput): Promise<HostEmployee> {
    const response = await this.apiClient.makeRequest({
      endpointConfig: API_ENDPOINTS.CREATE_HOST_EMPLOYEE,
      body: {
        email: input.email,
        fullName: input.fullName,
        employeeCode: input.employeeCode,
        departmentId: input.departmentId,
        phoneNumber: input.phoneNumber ?? null,
        designation: input.designation ?? null,
      },
      parserSchema: EmployeeResponseSchema,
    })
    const created = toHostEmployee(response.data)

    if (input.roleId) {
      const assigned = await this.assignRole(created.id, input.roleId, input.branchId)
      return { ...created, branchRoles: [...created.branchRoles, assigned] }
    }

    return created
  }

  async disable(employeeId: string): Promise<HostEmployee> {
    const response = await this.apiClient.makeRequest({
      endpointConfig: API_ENDPOINTS.DISABLE_HOST_EMPLOYEE,
      pathParams: { employeeId },
      parserSchema: EmployeeResponseSchema,
    })

    return toHostEmployee(response.data)
  }

  async enable(employeeId: string): Promise<HostEmployee> {
    const response = await this.apiClient.makeRequest({
      endpointConfig: API_ENDPOINTS.ENABLE_HOST_EMPLOYEE,
      pathParams: { employeeId },
      parserSchema: EmployeeResponseSchema,
    })

    return toHostEmployee(response.data)
  }

  async remove(employeeId: string): Promise<void> {
    await this.apiClient.makeRequest<unknown>({
      endpointConfig: API_ENDPOINTS.DELETE_HOST_EMPLOYEE,
      pathParams: { employeeId },
      parserSchema: z.unknown(),
    })
  }

  async listRoles(): Promise<RoleOut[]> {
    return fetchAllPages((page, pageSize) =>
      this.apiClient.makeRequest({
        endpointConfig: API_ENDPOINTS.LIST_ROLES,
        queryParams: { page, pageSize },
        parserSchema: RoleListResponseSchema,
      }),
    )
  }

  async listRolesPage({ page, pageSize }: ListRolesPageParams): Promise<RolesPage> {
    const response = await this.apiClient.makeRequest({
      endpointConfig: API_ENDPOINTS.LIST_ROLES,
      queryParams: { page, pageSize },
      parserSchema: RoleListResponseSchema,
    })

    return { items: response.data, total: response.pagination.total }
  }

  async createRole(input: RoleCreateInput): Promise<RoleOut> {
    const response = await this.apiClient.makeRequest({
      endpointConfig: API_ENDPOINTS.CREATE_ROLE,
      body: { name: input.name, description: input.description ?? null, permissionCodes: input.permissionCodes },
      parserSchema: RoleResponseSchema,
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

  async listPermissions(): Promise<PermissionOut[]> {
    // GET /auth/permissions is now paginated (paired add-listing-pagination-
    // filtering API change) - the permission-edit page's checklist UX needs
    // the whole catalog at once, not a paged subset, so request a page size
    // comfortably larger than the catalog (currently ~45 codes) in one call.
    const response = await this.apiClient.makeRequest({
      endpointConfig: API_ENDPOINTS.LIST_PERMISSIONS,
      queryParams: { pageSize: 100 },
      parserSchema: PermissionListResponseSchema,
    })

    return response.data
  }

  async updateRolePermissions(roleId: string, permissionCodes: string[]): Promise<RoleOut> {
    const response = await this.apiClient.makeRequest({
      endpointConfig: API_ENDPOINTS.UPDATE_ROLE,
      pathParams: { id: roleId },
      body: { permissionCodes },
      parserSchema: RoleResponseSchema,
    })

    return response.data
  }

  async resyncRolePermissions(): Promise<RolePermissionResyncEntry[]> {
    const response = await this.apiClient.makeRequest({
      endpointConfig: API_ENDPOINTS.RESYNC_ROLE_PERMISSIONS,
      parserSchema: RolePermissionResyncResponseSchema,
    })

    return response.data
  }
}

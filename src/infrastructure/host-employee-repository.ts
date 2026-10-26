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
import { EmployeeSyncResponseSchema, type EmployeeSyncItem } from '../domain/entities/employee-sync-schema'
import type { BranchRoleAssignment, HostEmployee, HostEmployeeCreateInput } from '../domain/entities/host-employee-schema'
import { RoleListResponseSchema, RoleResponseSchema, type RoleCreateInput, type RoleOut } from '../domain/entities/role-out-schema'
import {
  PermissionListResponseSchema,
  RolePermissionResyncResponseSchema,
  type PermissionOut,
  type RolePermissionResyncEntry,
} from '../domain/entities/permission-out-schema'
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

  async listPage({ page, pageSize, departmentId, role, status, search }: ListHostEmployeesPageParams): Promise<HostEmployeesPage> {
    const response = await this.apiClient.makeRequest({
      endpointConfig: API_ENDPOINTS.LIST_HOST_EMPLOYEES,
      queryParams: { page, pageSize, departmentId, role, status, search },
      parserSchema: EmployeeListResponseSchema,
    })

    return { items: response.data.map(toHostEmployee), total: response.pagination.total }
  }

  // The backend has no per-employee create endpoint — the employee directory
  // (what `list()` reads) is populated only via a company-wide sync that
  // replaces the whole roster. To add one employee without deactivating
  // everyone else, we re-send the full current roster plus the new entry.
  async create(input: HostEmployeeCreateInput): Promise<HostEmployee> {
    const existing = await this.list()

    // Employees synced in before employee codes were required may have no
    // code at all. Defaulting every one of them to the same '' would collide
    // in the batch (the backend rejects duplicate codes within one sync), so
    // fall back to a per-employee value derived from their unique id instead.
    const existingItems: EmployeeSyncItem[] = existing.map((employee) => ({
      email: employee.email,
      fullName: employee.fullName,
      employeeCode: employee.employeeCode ?? `EMP-${employee.id}`,
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

    // Credentials must exist before the sync: the sync registers the email, after
    // which POST /auth/users answers "Email already registered". The sync endpoint
    // itself has no password field, so it is expected to link the existing user.
    if (input.password) {
      await this.apiClient.makeRequest<unknown>({
        endpointConfig: API_ENDPOINTS.CREATE_STAFF_USER,
        body: { email: input.email, password: input.password, fullName: input.fullName },
        parserSchema: z.unknown(),
      })
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
    const response = await this.apiClient.makeRequest({
      endpointConfig: API_ENDPOINTS.LIST_ROLES,
      queryParams: { pageSize: 100 },
      parserSchema: RoleListResponseSchema,
    })

    return response.data
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

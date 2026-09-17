import type { BranchRoleAssignment, HostEmployee, HostEmployeeCreateInput } from '../../domain/entities/host-employee-schema'
import type { RoleCreateInput, RoleOut } from '../../domain/entities/role-out-schema'
import type { PermissionOut, RolePermissionResyncEntry } from '../../domain/entities/permission-out-schema'

export interface ListHostEmployeesPageParams {
  page: number
  pageSize: number
  departmentId?: string
  role?: string
  status?: 'active' | 'inactive'
}

export interface HostEmployeesPage {
  items: HostEmployee[]
  total: number
}

export interface ListRolesPageParams {
  page: number
  pageSize: number
}

export interface RolesPage {
  items: RoleOut[]
  total: number
}

export interface HostEmployeeRepository {
  list(): Promise<HostEmployee[]>
  listPage(params: ListHostEmployeesPageParams): Promise<HostEmployeesPage>
  create(input: HostEmployeeCreateInput): Promise<HostEmployee>
  listRoles(): Promise<RoleOut[]>
  listRolesPage(params: ListRolesPageParams): Promise<RolesPage>
  createRole(input: RoleCreateInput): Promise<RoleOut>
  assignRole(userId: string, roleId: string, branchId?: string): Promise<BranchRoleAssignment>
  revokeRole(userId: string, assignmentId: string): Promise<void>
  listPermissions(): Promise<PermissionOut[]>
  updateRolePermissions(roleId: string, permissionCodes: string[]): Promise<RoleOut>
  resyncRolePermissions(): Promise<RolePermissionResyncEntry[]>
}

import type { BranchRoleAssignment, HostEmployee, HostEmployeeCreateInput } from '../../domain/entities/host-employee-schema'
import type { RoleCreateInput, RoleOut } from '../../domain/entities/role-out-schema'
import type { PermissionOut, RolePermissionResyncEntry } from '../../domain/entities/permission-out-schema'

export interface HostEmployeeRepository {
  list(): Promise<HostEmployee[]>
  create(input: HostEmployeeCreateInput): Promise<HostEmployee>
  listRoles(): Promise<RoleOut[]>
  createRole(input: RoleCreateInput): Promise<RoleOut>
  assignRole(userId: string, roleId: string, branchId?: string): Promise<BranchRoleAssignment>
  revokeRole(userId: string, assignmentId: string): Promise<void>
  listPermissions(): Promise<PermissionOut[]>
  updateRolePermissions(roleId: string, permissionCodes: string[]): Promise<RoleOut>
  resyncRolePermissions(): Promise<RolePermissionResyncEntry[]>
}

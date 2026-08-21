import type { BranchRoleAssignment, HostEmployee, HostEmployeeCreateInput } from '../../domain/entities/host-employee-schema'
import type { RoleOut } from '../../domain/entities/role-out-schema'

export interface HostEmployeeRepository {
  list(): Promise<HostEmployee[]>
  create(input: HostEmployeeCreateInput): Promise<HostEmployee>
  listRoles(): Promise<RoleOut[]>
  assignRole(userId: string, roleId: string, branchId?: string): Promise<BranchRoleAssignment>
  revokeRole(userId: string, assignmentId: string): Promise<void>
}

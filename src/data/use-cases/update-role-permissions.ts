import type { HostEmployeeRepository } from '../repositories/host-employee-repository'
import type { RoleOut } from '../../domain/entities/role-out-schema'

export class UpdateRolePermissionsUseCase {
  private readonly hostEmployeeRepository: HostEmployeeRepository

  constructor(hostEmployeeRepository: HostEmployeeRepository) {
    this.hostEmployeeRepository = hostEmployeeRepository
  }

  async execute(roleId: string, permissionCodes: string[]): Promise<RoleOut> {
    return this.hostEmployeeRepository.updateRolePermissions(roleId, permissionCodes)
  }
}

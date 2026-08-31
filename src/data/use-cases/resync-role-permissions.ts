import type { HostEmployeeRepository } from '../repositories/host-employee-repository'
import type { RolePermissionResyncEntry } from '../../domain/entities/permission-out-schema'

export class ResyncRolePermissionsUseCase {
  private readonly hostEmployeeRepository: HostEmployeeRepository

  constructor(hostEmployeeRepository: HostEmployeeRepository) {
    this.hostEmployeeRepository = hostEmployeeRepository
  }

  async execute(): Promise<RolePermissionResyncEntry[]> {
    return this.hostEmployeeRepository.resyncRolePermissions()
  }
}

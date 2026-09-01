import type { HostEmployeeRepository } from '../repositories/host-employee-repository'
import type { PermissionOut } from '../../domain/entities/permission-out-schema'

export class ListPermissionsUseCase {
  private readonly hostEmployeeRepository: HostEmployeeRepository

  constructor(hostEmployeeRepository: HostEmployeeRepository) {
    this.hostEmployeeRepository = hostEmployeeRepository
  }

  async execute(): Promise<PermissionOut[]> {
    return this.hostEmployeeRepository.listPermissions()
  }
}

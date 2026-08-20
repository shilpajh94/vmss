import type { HostEmployeeRepository } from '../repositories/host-employee-repository'
import type { RoleOut } from '../../domain/entities/role-out-schema'

export class ListRolesUseCase {
  private readonly hostEmployeeRepository: HostEmployeeRepository

  constructor(hostEmployeeRepository: HostEmployeeRepository) {
    this.hostEmployeeRepository = hostEmployeeRepository
  }

  async execute(): Promise<RoleOut[]> {
    return this.hostEmployeeRepository.listRoles()
  }
}

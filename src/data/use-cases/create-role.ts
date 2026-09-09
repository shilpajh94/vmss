import type { HostEmployeeRepository } from '../repositories/host-employee-repository'
import type { RoleCreateInput, RoleOut } from '../../domain/entities/role-out-schema'

export class CreateRoleUseCase {
  private readonly hostEmployeeRepository: HostEmployeeRepository

  constructor(hostEmployeeRepository: HostEmployeeRepository) {
    this.hostEmployeeRepository = hostEmployeeRepository
  }

  async execute(input: RoleCreateInput): Promise<RoleOut> {
    return this.hostEmployeeRepository.createRole(input)
  }
}

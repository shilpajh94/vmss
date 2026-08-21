import type { HostEmployeeRepository } from '../repositories/host-employee-repository'
import type { BranchRoleAssignment } from '../../domain/entities/host-employee-schema'

export class AssignHostEmployeeRoleUseCase {
  private readonly hostEmployeeRepository: HostEmployeeRepository

  constructor(hostEmployeeRepository: HostEmployeeRepository) {
    this.hostEmployeeRepository = hostEmployeeRepository
  }

  async execute(userId: string, roleId: string, branchId?: string): Promise<BranchRoleAssignment> {
    return this.hostEmployeeRepository.assignRole(userId, roleId, branchId)
  }
}

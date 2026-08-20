import type { HostEmployeeRepository } from '../repositories/host-employee-repository'

export class RevokeHostEmployeeRoleUseCase {
  private readonly hostEmployeeRepository: HostEmployeeRepository

  constructor(hostEmployeeRepository: HostEmployeeRepository) {
    this.hostEmployeeRepository = hostEmployeeRepository
  }

  async execute(userId: string, assignmentId: string): Promise<void> {
    return this.hostEmployeeRepository.revokeRole(userId, assignmentId)
  }
}

import type { HostEmployeeRepository } from '../repositories/host-employee-repository'

export class DeleteHostEmployeeUseCase {
  private readonly hostEmployeeRepository: HostEmployeeRepository

  constructor(hostEmployeeRepository: HostEmployeeRepository) {
    this.hostEmployeeRepository = hostEmployeeRepository
  }

  async execute(employeeId: string): Promise<void> {
    return this.hostEmployeeRepository.remove(employeeId)
  }
}

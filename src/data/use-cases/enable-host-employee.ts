import type { HostEmployee } from '../../domain/entities/host-employee-schema'
import type { HostEmployeeRepository } from '../repositories/host-employee-repository'

export class EnableHostEmployeeUseCase {
  private readonly hostEmployeeRepository: HostEmployeeRepository

  constructor(hostEmployeeRepository: HostEmployeeRepository) {
    this.hostEmployeeRepository = hostEmployeeRepository
  }

  async execute(employeeId: string): Promise<HostEmployee> {
    return this.hostEmployeeRepository.enable(employeeId)
  }
}

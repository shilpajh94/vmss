import type { HostEmployeeRepository } from '../repositories/host-employee-repository'
import type { HostEmployee } from '../../domain/entities/host-employee-schema'

export class ListHostEmployeesUseCase {
  private readonly hostEmployeeRepository: HostEmployeeRepository

  constructor(hostEmployeeRepository: HostEmployeeRepository) {
    this.hostEmployeeRepository = hostEmployeeRepository
  }

  async execute(): Promise<HostEmployee[]> {
    return this.hostEmployeeRepository.list()
  }
}

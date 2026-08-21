import type { HostEmployeeRepository } from '../repositories/host-employee-repository'
import type { HostEmployee, HostEmployeeCreateInput } from '../../domain/entities/host-employee-schema'

export class CreateHostEmployeeUseCase {
  private readonly hostEmployeeRepository: HostEmployeeRepository

  constructor(hostEmployeeRepository: HostEmployeeRepository) {
    this.hostEmployeeRepository = hostEmployeeRepository
  }

  async execute(input: HostEmployeeCreateInput): Promise<HostEmployee> {
    return this.hostEmployeeRepository.create(input)
  }
}

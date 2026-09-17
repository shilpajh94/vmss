import type { HostEmployeeRepository, HostEmployeesPage, ListHostEmployeesPageParams } from '../repositories/host-employee-repository'

export class ListHostEmployeesPageUseCase {
  private readonly hostEmployeeRepository: HostEmployeeRepository

  constructor(hostEmployeeRepository: HostEmployeeRepository) {
    this.hostEmployeeRepository = hostEmployeeRepository
  }

  async execute(params: ListHostEmployeesPageParams): Promise<HostEmployeesPage> {
    return this.hostEmployeeRepository.listPage(params)
  }
}

import type { HostEmployeeRepository, ListRolesPageParams, RolesPage } from '../repositories/host-employee-repository'

export class ListRolesPageUseCase {
  private readonly hostEmployeeRepository: HostEmployeeRepository

  constructor(hostEmployeeRepository: HostEmployeeRepository) {
    this.hostEmployeeRepository = hostEmployeeRepository
  }

  async execute(params: ListRolesPageParams): Promise<RolesPage> {
    return this.hostEmployeeRepository.listRolesPage(params)
  }
}

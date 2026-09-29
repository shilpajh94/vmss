import type { DepartmentRepository, DepartmentsPage, ListDepartmentsPageParams } from '../repositories/department-repository'

export class ListDepartmentsPageUseCase {
  private readonly departmentRepository: DepartmentRepository

  constructor(departmentRepository: DepartmentRepository) {
    this.departmentRepository = departmentRepository
  }

  async execute(params: ListDepartmentsPageParams): Promise<DepartmentsPage> {
    return this.departmentRepository.listPage(params)
  }
}

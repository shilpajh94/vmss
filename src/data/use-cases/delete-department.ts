import type { DepartmentRepository } from '../repositories/department-repository'

export class DeleteDepartmentUseCase {
  private readonly departmentRepository: DepartmentRepository

  constructor(departmentRepository: DepartmentRepository) {
    this.departmentRepository = departmentRepository
  }

  async execute(id: string): Promise<void> {
    return this.departmentRepository.remove(id)
  }
}

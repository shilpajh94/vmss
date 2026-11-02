import type { DepartmentRepository } from '../repositories/department-repository'
import type { Department } from '../../domain/entities/department-schema'
import type { ListOptions } from '../repositories/list-options'

export class ListDepartmentsUseCase {
  private readonly departmentRepository: DepartmentRepository

  constructor(departmentRepository: DepartmentRepository) {
    this.departmentRepository = departmentRepository
  }

  async execute(options?: ListOptions): Promise<Department[]> {
    return this.departmentRepository.list(options)
  }
}

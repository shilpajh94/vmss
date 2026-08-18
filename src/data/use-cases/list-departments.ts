import type { DepartmentRepository } from '../repositories/department-repository'
import type { Department } from '../../domain/entities/department-schema'

export class ListDepartmentsUseCase {
  private readonly departmentRepository: DepartmentRepository

  constructor(departmentRepository: DepartmentRepository) {
    this.departmentRepository = departmentRepository
  }

  async execute(): Promise<Department[]> {
    return this.departmentRepository.list()
  }
}

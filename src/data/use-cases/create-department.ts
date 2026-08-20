import type { DepartmentRepository } from '../repositories/department-repository'
import type { Department } from '../../domain/entities/department-schema'

export class CreateDepartmentUseCase {
  private readonly departmentRepository: DepartmentRepository

  constructor(departmentRepository: DepartmentRepository) {
    this.departmentRepository = departmentRepository
  }

  async execute(input: Omit<Department, 'id' | 'branchName'>): Promise<Department> {
    return this.departmentRepository.create(input)
  }
}

import type { DepartmentRepository } from '../repositories/department-repository'
import type { Department } from '../../domain/entities/department-schema'

export class UpdateDepartmentUseCase {
  private readonly departmentRepository: DepartmentRepository

  constructor(departmentRepository: DepartmentRepository) {
    this.departmentRepository = departmentRepository
  }

  async execute(id: string, input: Omit<Department, 'id' | 'branchName'>): Promise<Department> {
    return this.departmentRepository.update(id, input)
  }
}

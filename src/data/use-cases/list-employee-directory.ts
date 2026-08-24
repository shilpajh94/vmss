import type { EmployeeDirectoryRepository } from '../repositories/employee-directory-repository'
import type { EmployeeDirectoryEntry } from '../../domain/entities/employee-directory-schema'

export class ListEmployeeDirectoryUseCase {
  private readonly employeeDirectoryRepository: EmployeeDirectoryRepository

  constructor(employeeDirectoryRepository: EmployeeDirectoryRepository) {
    this.employeeDirectoryRepository = employeeDirectoryRepository
  }

  async execute(): Promise<EmployeeDirectoryEntry[]> {
    return this.employeeDirectoryRepository.list()
  }
}

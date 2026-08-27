import type { EmployeeDirectoryEntry } from '../../domain/entities/employee-directory-schema'

export interface EmployeeDirectoryRepository {
  list(): Promise<EmployeeDirectoryEntry[]>
}

import type { Department } from '../../domain/entities/department-schema'

export interface DepartmentRepository {
  list(): Promise<Department[]>
  create(input: Omit<Department, 'id' | 'branchName'>): Promise<Department>
  update(id: string, input: Omit<Department, 'id' | 'branchName'>): Promise<Department>
  remove(id: string): Promise<void>
}

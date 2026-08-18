import type { Department, DepartmentInput } from '../../domain/entities/department-schema'

export interface DepartmentRepository {
  list(): Promise<Department[]>
  create(input: DepartmentInput): Promise<Department>
  update(id: string, input: DepartmentInput): Promise<Department>
  remove(id: string): Promise<void>
}

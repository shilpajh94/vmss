import type { Department } from '../../domain/entities/department-schema'
import type { ListOptions } from './list-options'

export interface ListDepartmentsPageParams {
  page: number
  pageSize: number
  status?: 'active' | 'inactive'
  /** No `branchId` query param exists on this endpoint - sent as `X-Branch-ID` instead. */
  branchId?: string
}

export interface DepartmentsPage {
  items: Department[]
  total: number
}

export interface DepartmentRepository {
  list(options?: ListOptions): Promise<Department[]>
  listPage(params: ListDepartmentsPageParams): Promise<DepartmentsPage>
  create(input: Omit<Department, 'id' | 'branchName'>): Promise<Department>
  update(id: string, input: Omit<Department, 'id' | 'branchName'>): Promise<Department>
  remove(id: string): Promise<void>
}

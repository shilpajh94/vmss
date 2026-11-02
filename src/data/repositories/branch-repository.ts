import type { Branch } from '../../domain/entities/branch-schema'
import type { ListOptions } from './list-options'

export interface ListBranchesPageParams {
  page: number
  pageSize: number
  status?: 'active' | 'inactive'
}

export interface BranchesPage {
  items: Branch[]
  total: number
}

export interface BranchRepository {
  /** Unfiltered, unpaginated (up to a generous cap) - for dropdown pickers. */
  list(options?: ListOptions): Promise<Branch[]>
  listPage(params: ListBranchesPageParams): Promise<BranchesPage>
  create(input: Omit<Branch, 'id'>): Promise<Branch>
  update(id: string, input: Omit<Branch, 'id'>): Promise<Branch>
  remove(id: string): Promise<void>
}

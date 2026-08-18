import type { Branch } from '../../domain/entities/branch-schema'

export interface BranchRepository {
  list(): Promise<Branch[]>
  create(input: Omit<Branch, 'id'>): Promise<Branch>
  update(id: string, input: Omit<Branch, 'id'>): Promise<Branch>
  remove(id: string): Promise<void>
}

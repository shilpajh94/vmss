import type { BranchRepository } from '../repositories/branch-repository'
import type { Branch } from '../../domain/entities/branch-schema'
import type { ListOptions } from '../repositories/list-options'

export class ListBranchesUseCase {
  private readonly branchRepository: BranchRepository

  constructor(branchRepository: BranchRepository) {
    this.branchRepository = branchRepository
  }

  async execute(options?: ListOptions): Promise<Branch[]> {
    return this.branchRepository.list(options)
  }
}

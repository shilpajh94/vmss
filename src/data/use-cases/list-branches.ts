import type { BranchRepository } from '../repositories/branch-repository'
import type { Branch } from '../../domain/entities/branch-schema'

export class ListBranchesUseCase {
  private readonly branchRepository: BranchRepository

  constructor(branchRepository: BranchRepository) {
    this.branchRepository = branchRepository
  }

  async execute(): Promise<Branch[]> {
    return this.branchRepository.list()
  }
}

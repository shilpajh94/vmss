import type { BranchRepository } from '../repositories/branch-repository'

export class DeleteBranchUseCase {
  private readonly branchRepository: BranchRepository

  constructor(branchRepository: BranchRepository) {
    this.branchRepository = branchRepository
  }

  async execute(id: string): Promise<void> {
    return this.branchRepository.remove(id)
  }
}

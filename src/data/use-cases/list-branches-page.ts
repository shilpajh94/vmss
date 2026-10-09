import type { BranchesPage, BranchRepository, ListBranchesPageParams } from '../repositories/branch-repository'

export class ListBranchesPageUseCase {
  private readonly branchRepository: BranchRepository

  constructor(branchRepository: BranchRepository) {
    this.branchRepository = branchRepository
  }

  async execute(params: ListBranchesPageParams): Promise<BranchesPage> {
    return this.branchRepository.listPage(params)
  }
}

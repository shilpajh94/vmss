import type { BranchRepository } from '../repositories/branch-repository'
import type { Branch } from '../../domain/entities/branch-schema'

export class UpdateBranchUseCase {
  private readonly branchRepository: BranchRepository

  constructor(branchRepository: BranchRepository) {
    this.branchRepository = branchRepository
  }

  async execute(id: string, input: Omit<Branch, 'id'>): Promise<Branch> {
    return this.branchRepository.update(id, input)
  }
}

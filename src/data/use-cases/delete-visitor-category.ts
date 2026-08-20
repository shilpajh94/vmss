import type { VisitorCategoryRepository } from '../repositories/visitor-category-repository'

export class DeleteVisitorCategoryUseCase {
  private readonly visitorCategoryRepository: VisitorCategoryRepository

  constructor(visitorCategoryRepository: VisitorCategoryRepository) {
    this.visitorCategoryRepository = visitorCategoryRepository
  }

  async execute(id: string): Promise<void> {
    return this.visitorCategoryRepository.remove(id)
  }
}

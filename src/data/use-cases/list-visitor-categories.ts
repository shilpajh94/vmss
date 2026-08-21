import type { VisitorCategoryRepository } from '../repositories/visitor-category-repository'
import type { VisitorCategory } from '../../domain/entities/visitor-category-schema'

export class ListVisitorCategoriesUseCase {
  private readonly visitorCategoryRepository: VisitorCategoryRepository

  constructor(visitorCategoryRepository: VisitorCategoryRepository) {
    this.visitorCategoryRepository = visitorCategoryRepository
  }

  async execute(): Promise<VisitorCategory[]> {
    return this.visitorCategoryRepository.list()
  }
}

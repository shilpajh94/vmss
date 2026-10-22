import type { VisitorCategoryRepository } from '../repositories/visitor-category-repository'
import type { VisitorCategory } from '../../domain/entities/visitor-category-schema'
import type { ListOptions } from '../repositories/list-options'

export class ListVisitorCategoriesUseCase {
  private readonly visitorCategoryRepository: VisitorCategoryRepository

  constructor(visitorCategoryRepository: VisitorCategoryRepository) {
    this.visitorCategoryRepository = visitorCategoryRepository
  }

  async execute(options?: ListOptions): Promise<VisitorCategory[]> {
    return this.visitorCategoryRepository.list(options)
  }
}

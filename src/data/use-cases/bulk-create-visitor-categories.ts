import type { VisitorCategoryRepository } from '../repositories/visitor-category-repository'
import type { VisitorCategoryBulkCreateOut } from '../../domain/entities/visitor-category-out-schema'
import type { VisitorCategoryBulkCreateInput } from '../../domain/entities/visitor-category-schema'

export class BulkCreateVisitorCategoriesUseCase {
  private readonly visitorCategoryRepository: VisitorCategoryRepository

  constructor(visitorCategoryRepository: VisitorCategoryRepository) {
    this.visitorCategoryRepository = visitorCategoryRepository
  }

  async execute(input: VisitorCategoryBulkCreateInput): Promise<VisitorCategoryBulkCreateOut> {
    return this.visitorCategoryRepository.bulkCreate(input)
  }
}

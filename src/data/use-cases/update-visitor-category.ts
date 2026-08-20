import type { VisitorCategoryRepository } from '../repositories/visitor-category-repository'
import type { VisitorCategory, VisitorCategoryInput } from '../../domain/entities/visitor-category-schema'

export class UpdateVisitorCategoryUseCase {
  private readonly visitorCategoryRepository: VisitorCategoryRepository

  constructor(visitorCategoryRepository: VisitorCategoryRepository) {
    this.visitorCategoryRepository = visitorCategoryRepository
  }

  async execute(id: string, input: VisitorCategoryInput): Promise<VisitorCategory> {
    return this.visitorCategoryRepository.update(id, input)
  }
}

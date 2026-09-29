import type {
  ListVisitorCategoriesPageParams,
  VisitorCategoriesPage,
  VisitorCategoryRepository,
} from '../repositories/visitor-category-repository'

export class ListVisitorCategoriesPageUseCase {
  private readonly visitorCategoryRepository: VisitorCategoryRepository

  constructor(visitorCategoryRepository: VisitorCategoryRepository) {
    this.visitorCategoryRepository = visitorCategoryRepository
  }

  async execute(params: ListVisitorCategoriesPageParams): Promise<VisitorCategoriesPage> {
    return this.visitorCategoryRepository.listPage(params)
  }
}

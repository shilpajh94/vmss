import type { VisitorCategory, VisitorCategoryInput } from '../../domain/entities/visitor-category-schema'

export interface ListVisitorCategoriesPageParams {
  page: number
  pageSize: number
  badgeColor?: string
  ndaRequirement?: string
  escortRequirement?: string
}

export interface VisitorCategoriesPage {
  items: VisitorCategory[]
  total: number
}

export interface VisitorCategoryRepository {
  list(): Promise<VisitorCategory[]>
  listPage(params: ListVisitorCategoriesPageParams): Promise<VisitorCategoriesPage>
  create(input: VisitorCategoryInput): Promise<VisitorCategory>
  update(id: string, input: VisitorCategoryInput): Promise<VisitorCategory>
  remove(id: string): Promise<void>
}

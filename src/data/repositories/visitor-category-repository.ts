import type { VisitorCategoryBulkCreateOut } from '../../domain/entities/visitor-category-out-schema'
import type {
  VisitorCategory,
  VisitorCategoryBulkCreateInput,
  VisitorCategoryInput,
} from '../../domain/entities/visitor-category-schema'
import type { ListOptions } from './list-options'

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
  list(options?: ListOptions): Promise<VisitorCategory[]>
  listPage(params: ListVisitorCategoriesPageParams): Promise<VisitorCategoriesPage>
  create(input: VisitorCategoryInput): Promise<VisitorCategory>
  bulkCreate(input: VisitorCategoryBulkCreateInput): Promise<VisitorCategoryBulkCreateOut>
  update(id: string, input: VisitorCategoryInput): Promise<VisitorCategory>
  remove(id: string): Promise<void>
}

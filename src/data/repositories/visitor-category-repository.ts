import type { VisitorCategory, VisitorCategoryInput } from '../../domain/entities/visitor-category-schema'

export interface VisitorCategoryRepository {
  list(): Promise<VisitorCategory[]>
  create(input: VisitorCategoryInput): Promise<VisitorCategory>
  update(id: string, input: VisitorCategoryInput): Promise<VisitorCategory>
  remove(id: string): Promise<void>
}

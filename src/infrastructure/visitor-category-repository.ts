import z from 'zod'
import { API_ENDPOINTS } from '../data/api/api-endpoints'
import type { ApiClient } from '../data/api/api-client'
import type {
  ListVisitorCategoriesPageParams,
  VisitorCategoriesPage,
  VisitorCategoryRepository,
} from '../data/repositories/visitor-category-repository'
import {
  VisitorCategoryListResponseSchema,
  VisitorCategoryResponseSchema,
  type VisitorCategoryOut,
} from '../domain/entities/visitor-category-out-schema'
import type { VisitorCategory, VisitorCategoryInput } from '../domain/entities/visitor-category-schema'

function toVisitorCategory(visitorCategoryOut: VisitorCategoryOut): VisitorCategory {
  return {
    id: visitorCategoryOut.id,
    name: visitorCategoryOut.name,
    code: visitorCategoryOut.code,
    description: visitorCategoryOut.description ?? undefined,
    // The backend allows a category to have no badge color; the domain type
    // doesn't model that (VisitorCategorySchema's own `.default('blue')`),
    // so a null wire value is defaulted here at the parsing boundary instead
    // of propagating null through every consumer of `VisitorCategory`.
    badgeColor: visitorCategoryOut.badgeColor ?? 'blue',
    ndaRequirement: visitorCategoryOut.ndaRequirement ?? undefined,
    escortRequirement: visitorCategoryOut.escortRequirement ?? undefined,
    maxDurationMinutes: visitorCategoryOut.maxDurationMinutes ?? undefined,
  }
}

export class HttpVisitorCategoryRepository implements VisitorCategoryRepository {
  private readonly apiClient: ApiClient

  constructor(apiClient: ApiClient) {
    this.apiClient = apiClient
  }

  async list(): Promise<VisitorCategory[]> {
    const response = await this.apiClient.makeRequest({
      endpointConfig: API_ENDPOINTS.LIST_VISITOR_CATEGORIES,
      queryParams: { pageSize: 100 },
      parserSchema: VisitorCategoryListResponseSchema,
    })

    return response.data.map(toVisitorCategory)
  }

  async listPage({ page, pageSize, badgeColor, ndaRequirement, escortRequirement }: ListVisitorCategoriesPageParams): Promise<VisitorCategoriesPage> {
    const response = await this.apiClient.makeRequest({
      endpointConfig: API_ENDPOINTS.LIST_VISITOR_CATEGORIES,
      queryParams: { page, pageSize, badgeColor, ndaRequirement, escortRequirement },
      parserSchema: VisitorCategoryListResponseSchema,
    })

    return { items: response.data.map(toVisitorCategory), total: response.pagination.total }
  }

  async create(input: VisitorCategoryInput): Promise<VisitorCategory> {
    const response = await this.apiClient.makeRequest({
      endpointConfig: API_ENDPOINTS.CREATE_VISITOR_CATEGORY,
      body: {
        name: input.name,
        code: input.code,
        description: input.description ?? null,
        badgeColor: input.badgeColor,
        ndaRequirement: input.ndaRequirement ?? null,
        escortRequirement: input.escortRequirement ?? null,
        maxDurationMinutes: input.maxDurationMinutes ?? null,
      },
      parserSchema: VisitorCategoryResponseSchema,
    })

    return toVisitorCategory(response.data)
  }

  async update(id: string, input: VisitorCategoryInput): Promise<VisitorCategory> {
    const response = await this.apiClient.makeRequest({
      endpointConfig: API_ENDPOINTS.UPDATE_VISITOR_CATEGORY,
      body: {
        name: input.name,
        code: input.code,
        description: input.description ?? null,
        badgeColor: input.badgeColor,
        ndaRequirement: input.ndaRequirement ?? null,
        escortRequirement: input.escortRequirement ?? null,
        maxDurationMinutes: input.maxDurationMinutes ?? null,
      },
      pathParams: { id },
      parserSchema: VisitorCategoryResponseSchema,
    })

    return toVisitorCategory(response.data)
  }

  async remove(id: string): Promise<void> {
    await this.apiClient.makeRequest<unknown>({
      endpointConfig: API_ENDPOINTS.DELETE_VISITOR_CATEGORY,
      pathParams: { id },
      parserSchema: z.unknown(),
    })
  }
}

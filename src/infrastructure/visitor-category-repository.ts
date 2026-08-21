import z from 'zod'
import { API_ENDPOINTS } from '../data/api/api-endpoints'
import type { ApiClient } from '../data/api/api-client'
import type { VisitorCategoryRepository } from '../data/repositories/visitor-category-repository'
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
    description: visitorCategoryOut.description ?? undefined,
    badgeColor: visitorCategoryOut.badgeColor,
    ndaRequired: visitorCategoryOut.ndaRequired ?? undefined,
    escortRequired: visitorCategoryOut.escortRequired ?? undefined,
    maxDuration: visitorCategoryOut.maxDuration ?? undefined,
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

  async create(input: VisitorCategoryInput): Promise<VisitorCategory> {
    const response = await this.apiClient.makeRequest({
      endpointConfig: API_ENDPOINTS.CREATE_VISITOR_CATEGORY,
      body: {
        name: input.name,
        description: input.description ?? null,
        badgeColor: input.badgeColor,
        ndaRequired: input.ndaRequired ?? null,
        escortRequired: input.escortRequired ?? null,
        maxDuration: input.maxDuration ?? null,
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
        description: input.description ?? null,
        badgeColor: input.badgeColor,
        ndaRequired: input.ndaRequired ?? null,
        escortRequired: input.escortRequired ?? null,
        maxDuration: input.maxDuration ?? null,
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

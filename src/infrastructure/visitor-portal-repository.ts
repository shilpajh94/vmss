import { API_ENDPOINTS } from '../data/api/api-endpoints'
import type { ApiClient } from '../data/api/api-client'
import type { VisitorPortalPageParams, VisitorPortalRepository } from '../data/repositories/visitor-portal-repository'
import { VisitorPortalMeResponseSchema, type VisitorPortalMe } from '../domain/entities/visitor-portal-schema'

export class HttpVisitorPortalRepository implements VisitorPortalRepository {
  private readonly apiClient: ApiClient

  constructor(apiClient: ApiClient) {
    this.apiClient = apiClient
  }

  async getMe(proofToken: string, page?: VisitorPortalPageParams): Promise<VisitorPortalMe> {
    const response = await this.apiClient.makeRequest({
      endpointConfig: API_ENDPOINTS.GET_VISITOR_PORTAL_ME,
      // Router query params (`page`, `page_size`) are plain FastAPI function
      // args, not a CamelModel body — unlike the JSON response, they are NOT
      // camelCased on the wire.
      queryParams: page ? { page: page.page, page_size: page.pageSize } : undefined,
      headers: { Authorization: `Bearer ${proofToken}` },
      parserSchema: VisitorPortalMeResponseSchema,
    })
    return response.data
  }
}

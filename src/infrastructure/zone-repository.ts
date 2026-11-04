import z from 'zod'
import { API_ENDPOINTS } from '../data/api/api-endpoints'
import type { ApiClient } from '../data/api/api-client'
import type { ListZonesParams, ZoneRepository } from '../data/repositories/zone-repository'
import {
  ZoneIdsResponseSchema,
  ZoneListResponseSchema,
  ZoneResponseSchema,
  type Zone,
  type ZoneInput,
  type ZoneListResponse,
} from '../domain/entities/zone-schema'

export class HttpZoneRepository implements ZoneRepository {
  private readonly apiClient: ApiClient

  constructor(apiClient: ApiClient) {
    this.apiClient = apiClient
  }

  list({ page, pageSize, isActive, sortBy, sortOrder, branchId }: ListZonesParams): Promise<ZoneListResponse> {
    return this.apiClient.makeRequest({
      endpointConfig: API_ENDPOINTS.LIST_ZONES,
      queryParams: { page, pageSize, isActive, sortBy, sortOrder },
      headers: branchId ? { 'X-Branch-ID': branchId } : undefined,
      parserSchema: ZoneListResponseSchema,
    })
  }

  async get(id: string): Promise<Zone> {
    const response = await this.apiClient.makeRequest({
      endpointConfig: API_ENDPOINTS.GET_ZONE,
      pathParams: { id },
      parserSchema: ZoneResponseSchema,
    })
    return response.data
  }

  async create(input: ZoneInput): Promise<Zone> {
    const response = await this.apiClient.makeRequest({
      endpointConfig: API_ENDPOINTS.CREATE_ZONE,
      body: input,
      parserSchema: ZoneResponseSchema,
    })
    return response.data
  }

  async update(id: string, input: Omit<ZoneInput, 'branchId'>): Promise<Zone> {
    const response = await this.apiClient.makeRequest({
      endpointConfig: API_ENDPOINTS.UPDATE_ZONE,
      pathParams: { id },
      body: input,
      parserSchema: ZoneResponseSchema,
    })
    return response.data
  }

  async remove(id: string): Promise<void> {
    await this.apiClient.makeRequest<unknown>({
      endpointConfig: API_ENDPOINTS.DELETE_ZONE,
      pathParams: { id },
      parserSchema: z.unknown(),
    })
  }

  getCategoryZoneIds(categoryId: string): Promise<string[]> {
    return this.apiClient.makeRequest({
      endpointConfig: API_ENDPOINTS.GET_CATEGORY_ZONES,
      pathParams: { id: categoryId },
      parserSchema: ZoneIdsResponseSchema,
    })
  }

  setCategoryZoneIds(categoryId: string, zoneIds: string[]): Promise<string[]> {
    return this.apiClient.makeRequest({
      endpointConfig: API_ENDPOINTS.SET_CATEGORY_ZONES,
      pathParams: { id: categoryId },
      body: { zoneIds },
      parserSchema: ZoneIdsResponseSchema,
    })
  }

  getInvitationZoneIds(invitationId: string): Promise<string[]> {
    return this.apiClient.makeRequest({
      endpointConfig: API_ENDPOINTS.GET_INVITATION_ZONES,
      pathParams: { id: invitationId },
      parserSchema: ZoneIdsResponseSchema,
    })
  }

  setInvitationZoneIds(invitationId: string, zoneIds: string[]): Promise<string[]> {
    return this.apiClient.makeRequest({
      endpointConfig: API_ENDPOINTS.SET_INVITATION_ZONES,
      pathParams: { id: invitationId },
      body: { zoneIds },
      parserSchema: ZoneIdsResponseSchema,
    })
  }
}

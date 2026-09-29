import z from 'zod'
import { API_ENDPOINTS } from '../data/api/api-endpoints'
import type { ApiClient } from '../data/api/api-client'
import type { KioskRepository, KiosksPage, ListKiosksPageParams } from '../data/repositories/kiosk-repository'
import { KioskListResponseSchema, KioskResponseSchema, type Kiosk, type KioskInput } from '../domain/entities/kiosk-schema'

export class HttpKioskRepository implements KioskRepository {
  private readonly apiClient: ApiClient

  constructor(apiClient: ApiClient) {
    this.apiClient = apiClient
  }

  async listPage({ page, pageSize, status, includeHidden, sortBy, sortOrder }: ListKiosksPageParams): Promise<KiosksPage> {
    const response = await this.apiClient.makeRequest({
      endpointConfig: API_ENDPOINTS.LIST_KIOSKS,
      queryParams: { page, pageSize, status, includeHidden, sortBy, sortOrder },
      parserSchema: KioskListResponseSchema,
    })

    return { items: response.data, total: response.pagination.total }
  }

  async get(id: string): Promise<Kiosk> {
    const response = await this.apiClient.makeRequest({
      endpointConfig: API_ENDPOINTS.GET_KIOSK,
      pathParams: { id },
      parserSchema: KioskResponseSchema,
    })

    return response.data
  }

  async create(input: KioskInput): Promise<Kiosk> {
    const response = await this.apiClient.makeRequest({
      endpointConfig: API_ENDPOINTS.CREATE_KIOSK,
      body: input,
      parserSchema: KioskResponseSchema,
    })

    return response.data
  }

  async update(id: string, input: Partial<KioskInput>): Promise<Kiosk> {
    const response = await this.apiClient.makeRequest({
      endpointConfig: API_ENDPOINTS.UPDATE_KIOSK,
      pathParams: { id },
      body: input,
      parserSchema: KioskResponseSchema,
    })

    return response.data
  }

  async setHidden(id: string, isHidden: boolean): Promise<Kiosk> {
    const response = await this.apiClient.makeRequest({
      endpointConfig: API_ENDPOINTS.SET_KIOSK_VISIBILITY,
      pathParams: { id },
      body: { isHidden },
      parserSchema: KioskResponseSchema,
    })

    return response.data
  }

  async remove(id: string): Promise<void> {
    await this.apiClient.makeRequest<unknown>({
      endpointConfig: API_ENDPOINTS.DELETE_KIOSK,
      pathParams: { id },
      parserSchema: z.unknown(),
    })
  }
}

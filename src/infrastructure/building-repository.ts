import z from 'zod'
import { API_ENDPOINTS } from '../data/api/api-endpoints'
import type { ApiClient } from '../data/api/api-client'
import type { BuildingRepository } from '../data/repositories/building-repository'
import { BuildingSchema, type Building, type BuildingInput } from '../domain/entities/building-schema'

export class HttpBuildingRepository implements BuildingRepository {
  private readonly apiClient: ApiClient

  constructor(apiClient: ApiClient) {
    this.apiClient = apiClient
  }

  async list(): Promise<Building[]> {
    return this.apiClient.makeRequest<Building[]>({
      endpointConfig: API_ENDPOINTS.LIST_BUILDINGS,
      parserSchema: z.array(BuildingSchema),
    })
  }

  async create(input: BuildingInput): Promise<Building> {
    return this.apiClient.makeRequest<Building>({
      endpointConfig: API_ENDPOINTS.CREATE_BUILDING,
      body: input,
      parserSchema: BuildingSchema,
    })
  }

  async update(id: string, input: BuildingInput): Promise<Building> {
    return this.apiClient.makeRequest<Building>({
      endpointConfig: API_ENDPOINTS.UPDATE_BUILDING,
      body: input,
      queryParams: { id },
      parserSchema: BuildingSchema,
    })
  }

  async remove(id: string): Promise<void> {
    await this.apiClient.makeRequest<unknown>({
      endpointConfig: API_ENDPOINTS.DELETE_BUILDING,
      queryParams: { id },
      parserSchema: z.unknown(),
    })
  }
}

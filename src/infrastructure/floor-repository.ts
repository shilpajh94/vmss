import z from 'zod'
import { API_ENDPOINTS } from '../data/api/api-endpoints'
import type { ApiClient } from '../data/api/api-client'
import type { FloorRepository, FloorsPage, ListFloorsPageParams } from '../data/repositories/floor-repository'
import { FloorListResponseSchema, FloorResponseSchema, type FloorOut } from '../domain/entities/floor-out-schema'
import type { Floor, FloorInput } from '../domain/entities/floor-schema'
import { fetchAllPages } from '../data/api/fetch-all-pages'
import type { ListOptions } from '../data/repositories/list-options'

function toFloor(floorOut: FloorOut): Floor {
  return {
    id: floorOut.id,
    buildingId: floorOut.buildingId,
    name: floorOut.name,
    floorNumber: floorOut.floorNumber,
    isActive: floorOut.isActive,
    capacity: floorOut.capacity ?? 0,
    capacityType: floorOut.capacityType ?? 'guests',
    accessLevel: floorOut.accessLevel ?? 'public',
  }
}

export class HttpFloorRepository implements FloorRepository {
  private readonly apiClient: ApiClient

  constructor(apiClient: ApiClient) {
    this.apiClient = apiClient
  }

  async list(buildingId?: string, options?: ListOptions): Promise<Floor[]> {
    const floors = await fetchAllPages((page, pageSize) =>
      this.apiClient.makeRequest({
        endpointConfig: API_ENDPOINTS.LIST_FLOORS,
        queryParams: { page, pageSize, buildingId, status: options?.activeOnly ? 'active' : undefined },
        parserSchema: FloorListResponseSchema,
      }),
    )

    return floors.map(toFloor)
  }

  async listPage({ page, pageSize, buildingId, status, accessLevel }: ListFloorsPageParams): Promise<FloorsPage> {
    const response = await this.apiClient.makeRequest({
      endpointConfig: API_ENDPOINTS.LIST_FLOORS,
      queryParams: { page, pageSize, buildingId, status, accessLevel },
      parserSchema: FloorListResponseSchema,
    })

    return { items: response.data.map(toFloor), total: response.pagination.total }
  }

  async create(input: FloorInput): Promise<Floor> {
    const response = await this.apiClient.makeRequest({
      endpointConfig: API_ENDPOINTS.CREATE_FLOOR,
      body: {
        buildingId: input.buildingId,
        name: input.name,
        floorNumber: input.floorNumber,
        capacity: input.capacity,
        capacityType: input.capacityType,
        accessLevel: input.accessLevel,
      },
      parserSchema: FloorResponseSchema,
    })

    return toFloor(response.data)
  }

  async update(id: string, input: FloorInput): Promise<Floor> {
    const response = await this.apiClient.makeRequest({
      endpointConfig: API_ENDPOINTS.UPDATE_FLOOR,
      body: {
        name: input.name,
        floorNumber: input.floorNumber,
        isActive: input.isActive,
        capacity: input.capacity,
        capacityType: input.capacityType,
        accessLevel: input.accessLevel,
      },
      pathParams: { id },
      parserSchema: FloorResponseSchema,
    })

    return toFloor(response.data)
  }

  async remove(id: string): Promise<void> {
    await this.apiClient.makeRequest<unknown>({
      endpointConfig: API_ENDPOINTS.DELETE_FLOOR,
      pathParams: { id },
      parserSchema: z.unknown(),
    })
  }
}

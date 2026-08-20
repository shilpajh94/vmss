import z from 'zod'
import { API_ENDPOINTS } from '../data/api/api-endpoints'
import type { ApiClient } from '../data/api/api-client'
import type { BuildingRepository } from '../data/repositories/building-repository'
import type { FloorRepository } from '../data/repositories/floor-repository'
import type { SecurityGateRepository } from '../data/repositories/security-gate-repository'
import {
  SecurityGateListResponseSchema,
  SecurityGateResponseSchema,
  type SecurityGateOut,
} from '../domain/entities/security-gate-out-schema'
import type { SecurityGate, SecurityGateInput } from '../domain/entities/security-gate-schema'

interface NameLookups {
  buildingNameById: Map<string, string>
  floorNameById: Map<string, string>
}

export class HttpSecurityGateRepository implements SecurityGateRepository {
  private readonly apiClient: ApiClient
  private readonly buildingRepository: BuildingRepository
  private readonly floorRepository: FloorRepository

  constructor(apiClient: ApiClient, buildingRepository: BuildingRepository, floorRepository: FloorRepository) {
    this.apiClient = apiClient
    this.buildingRepository = buildingRepository
    this.floorRepository = floorRepository
  }

  private async buildNameLookups(): Promise<NameLookups> {
    const [buildings, floors] = await Promise.all([this.buildingRepository.list(), this.floorRepository.list()])

    return {
      buildingNameById: new Map(buildings.map((building) => [building.id, building.name])),
      floorNameById: new Map(floors.map((floor) => [floor.id, floor.name])),
    }
  }

  private toSecurityGate(securityGateOut: SecurityGateOut, lookups: NameLookups): SecurityGate {
    const floorId = securityGateOut.floorId ?? undefined

    return {
      id: securityGateOut.id,
      buildingId: securityGateOut.buildingId,
      buildingName: lookups.buildingNameById.get(securityGateOut.buildingId) ?? '',
      floorId,
      floorName: floorId ? lookups.floorNameById.get(floorId) : undefined,
      name: securityGateOut.name,
      gateType: securityGateOut.gateType,
      authMethod: securityGateOut.authMethod ?? undefined,
      connectivityStatus: securityGateOut.connectivityStatus,
    }
  }

  async list(): Promise<SecurityGate[]> {
    const [response, lookups] = await Promise.all([
      this.apiClient.makeRequest({
        endpointConfig: API_ENDPOINTS.LIST_SECURITY_GATES,
        queryParams: { pageSize: 100 },
        parserSchema: SecurityGateListResponseSchema,
      }),
      this.buildNameLookups(),
    ])

    return response.data.map((securityGateOut) => this.toSecurityGate(securityGateOut, lookups))
  }

  async create(input: SecurityGateInput): Promise<SecurityGate> {
    const [response, lookups] = await Promise.all([
      this.apiClient.makeRequest({
        endpointConfig: API_ENDPOINTS.CREATE_SECURITY_GATE,
        body: {
          buildingId: input.buildingId,
          floorId: input.floorId ?? null,
          name: input.name,
          gateType: input.gateType,
          authMethod: input.authMethod ?? null,
          connectivityStatus: input.connectivityStatus,
        },
        parserSchema: SecurityGateResponseSchema,
      }),
      this.buildNameLookups(),
    ])

    return this.toSecurityGate(response.data, lookups)
  }

  async update(id: string, input: SecurityGateInput): Promise<SecurityGate> {
    const [response, lookups] = await Promise.all([
      this.apiClient.makeRequest({
        endpointConfig: API_ENDPOINTS.UPDATE_SECURITY_GATE,
        body: {
          buildingId: input.buildingId,
          floorId: input.floorId ?? null,
          name: input.name,
          gateType: input.gateType,
          authMethod: input.authMethod ?? null,
          connectivityStatus: input.connectivityStatus,
        },
        pathParams: { id },
        parserSchema: SecurityGateResponseSchema,
      }),
      this.buildNameLookups(),
    ])

    return this.toSecurityGate(response.data, lookups)
  }

  async remove(id: string): Promise<void> {
    await this.apiClient.makeRequest<unknown>({
      endpointConfig: API_ENDPOINTS.DELETE_SECURITY_GATE,
      pathParams: { id },
      parserSchema: z.unknown(),
    })
  }
}

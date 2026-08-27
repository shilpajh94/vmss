import z from 'zod'
import { API_ENDPOINTS } from '../data/api/api-endpoints'
import type { ApiClient } from '../data/api/api-client'
import type { BuildingRepository } from '../data/repositories/building-repository'
import type { SecurityGateRepository } from '../data/repositories/security-gate-repository'
import {
  SecurityGateListResponseSchema,
  SecurityGateResponseSchema,
  type SecurityGateOut,
} from '../domain/entities/security-gate-out-schema'
import type { Building } from '../domain/entities/building-schema'
import type { SecurityGate, SecurityGateInput } from '../domain/entities/security-gate-schema'

interface NameLookups {
  buildingById: Map<string, Building>
}

export class HttpSecurityGateRepository implements SecurityGateRepository {
  private readonly apiClient: ApiClient
  private readonly buildingRepository: BuildingRepository

  constructor(apiClient: ApiClient, buildingRepository: BuildingRepository) {
    this.apiClient = apiClient
    this.buildingRepository = buildingRepository
  }

  private async buildNameLookups(): Promise<NameLookups> {
    const buildings = await this.buildingRepository.list()

    return {
      buildingById: new Map(buildings.map((building) => [building.id, building])),
    }
  }

  private toSecurityGate(securityGateOut: SecurityGateOut, lookups: NameLookups): SecurityGate {
    const building = securityGateOut.buildingId ? lookups.buildingById.get(securityGateOut.buildingId) : undefined

    return {
      id: securityGateOut.id,
      buildingId: securityGateOut.buildingId ?? '',
      buildingName: building?.name ?? '',
      name: securityGateOut.name,
      code: securityGateOut.code,
      gateType: securityGateOut.gateType,
      highSecurity: securityGateOut.highSecurity,
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
    const lookups = await this.buildNameLookups()
    const branchId = lookups.buildingById.get(input.buildingId)?.branchId
    if (!branchId) throw new Error(`Unknown building: ${input.buildingId}`)

    const response = await this.apiClient.makeRequest({
      endpointConfig: API_ENDPOINTS.CREATE_SECURITY_GATE,
      body: {
        branchId,
        buildingId: input.buildingId,
        name: input.name,
        code: input.code,
        gateType: input.gateType,
        highSecurity: input.highSecurity,
      },
      parserSchema: SecurityGateResponseSchema,
    })

    return this.toSecurityGate(response.data, lookups)
  }

  async update(id: string, input: SecurityGateInput): Promise<SecurityGate> {
    // The backend's update contract has no branchId field — a gate's branch can't change after creation.
    const [response, lookups] = await Promise.all([
      this.apiClient.makeRequest({
        endpointConfig: API_ENDPOINTS.UPDATE_SECURITY_GATE,
        body: {
          buildingId: input.buildingId,
          name: input.name,
          code: input.code,
          gateType: input.gateType,
          highSecurity: input.highSecurity,
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

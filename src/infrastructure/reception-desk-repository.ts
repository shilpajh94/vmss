import z from 'zod'
import { API_ENDPOINTS } from '../data/api/api-endpoints'
import type { ApiClient } from '../data/api/api-client'
import type { BuildingRepository } from '../data/repositories/building-repository'
import type { FloorRepository } from '../data/repositories/floor-repository'
import type { HostEmployeeRepository } from '../data/repositories/host-employee-repository'
import type { ReceptionDeskRepository } from '../data/repositories/reception-desk-repository'
import {
  ReceptionDeskListResponseSchema,
  ReceptionDeskResponseSchema,
  type ReceptionDeskOut,
} from '../domain/entities/reception-desk-out-schema'
import type { ReceptionDesk, ReceptionDeskInput } from '../domain/entities/reception-desk-schema'

interface NameLookups {
  buildingNameById: Map<string, string>
  floorNameById: Map<string, string>
  receptionistNameById: Map<string, string>
}

export class HttpReceptionDeskRepository implements ReceptionDeskRepository {
  private readonly apiClient: ApiClient
  private readonly buildingRepository: BuildingRepository
  private readonly floorRepository: FloorRepository
  private readonly hostEmployeeRepository: HostEmployeeRepository

  constructor(
    apiClient: ApiClient,
    buildingRepository: BuildingRepository,
    floorRepository: FloorRepository,
    hostEmployeeRepository: HostEmployeeRepository,
  ) {
    this.apiClient = apiClient
    this.buildingRepository = buildingRepository
    this.floorRepository = floorRepository
    this.hostEmployeeRepository = hostEmployeeRepository
  }

  private async buildNameLookups(): Promise<NameLookups> {
    const [buildings, floors, hostEmployees] = await Promise.all([
      this.buildingRepository.list(),
      this.floorRepository.list(),
      this.hostEmployeeRepository.list(),
    ])

    return {
      buildingNameById: new Map(buildings.map((building) => [building.id, building.name])),
      floorNameById: new Map(floors.map((floor) => [floor.id, floor.name])),
      receptionistNameById: new Map(hostEmployees.map((employee) => [employee.id, employee.fullName])),
    }
  }

  private toReceptionDesk(receptionDeskOut: ReceptionDeskOut, lookups: NameLookups): ReceptionDesk {
    const floorId = receptionDeskOut.floorId ?? undefined
    const receptionistUserId = receptionDeskOut.receptionistUserId ?? undefined

    return {
      id: receptionDeskOut.id,
      buildingId: receptionDeskOut.buildingId,
      buildingName: lookups.buildingNameById.get(receptionDeskOut.buildingId) ?? '',
      floorId,
      floorName: floorId ? lookups.floorNameById.get(floorId) : undefined,
      name: receptionDeskOut.name,
      receptionistUserId,
      receptionistName: receptionistUserId ? lookups.receptionistNameById.get(receptionistUserId) : undefined,
      operatingHoursFrom: receptionDeskOut.operatingHoursFrom ?? undefined,
      operatingHoursTo: receptionDeskOut.operatingHoursTo ?? undefined,
      status: receptionDeskOut.status,
    }
  }

  async list(): Promise<ReceptionDesk[]> {
    const [response, lookups] = await Promise.all([
      this.apiClient.makeRequest({
        endpointConfig: API_ENDPOINTS.LIST_RECEPTION_DESKS,
        queryParams: { pageSize: 100 },
        parserSchema: ReceptionDeskListResponseSchema,
      }),
      this.buildNameLookups(),
    ])

    return response.data.map((receptionDeskOut) => this.toReceptionDesk(receptionDeskOut, lookups))
  }

  async create(input: ReceptionDeskInput): Promise<ReceptionDesk> {
    const [response, lookups] = await Promise.all([
      this.apiClient.makeRequest({
        endpointConfig: API_ENDPOINTS.CREATE_RECEPTION_DESK,
        body: {
          buildingId: input.buildingId,
          floorId: input.floorId ?? null,
          name: input.name,
          receptionistUserId: input.receptionistUserId ?? null,
          operatingHoursFrom: input.operatingHoursFrom ?? null,
          operatingHoursTo: input.operatingHoursTo ?? null,
          status: input.status,
        },
        parserSchema: ReceptionDeskResponseSchema,
      }),
      this.buildNameLookups(),
    ])

    return this.toReceptionDesk(response.data, lookups)
  }

  async update(id: string, input: ReceptionDeskInput): Promise<ReceptionDesk> {
    const [response, lookups] = await Promise.all([
      this.apiClient.makeRequest({
        endpointConfig: API_ENDPOINTS.UPDATE_RECEPTION_DESK,
        body: {
          buildingId: input.buildingId,
          floorId: input.floorId ?? null,
          name: input.name,
          receptionistUserId: input.receptionistUserId ?? null,
          operatingHoursFrom: input.operatingHoursFrom ?? null,
          operatingHoursTo: input.operatingHoursTo ?? null,
          status: input.status,
        },
        pathParams: { id },
        parserSchema: ReceptionDeskResponseSchema,
      }),
      this.buildNameLookups(),
    ])

    return this.toReceptionDesk(response.data, lookups)
  }

  async remove(id: string): Promise<void> {
    await this.apiClient.makeRequest<unknown>({
      endpointConfig: API_ENDPOINTS.DELETE_RECEPTION_DESK,
      pathParams: { id },
      parserSchema: z.unknown(),
    })
  }
}

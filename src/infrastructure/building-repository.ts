import z from 'zod'
import { API_ENDPOINTS } from '../data/api/api-endpoints'
import type { ApiClient } from '../data/api/api-client'
import type { BranchRepository } from '../data/repositories/branch-repository'
import type { BuildingRepository, BuildingsPage, ListBuildingsPageParams } from '../data/repositories/building-repository'
import { BuildingListResponseSchema, BuildingResponseSchema, type BuildingOut } from '../domain/entities/building-out-schema'
import type { Building, BuildingInput } from '../domain/entities/building-schema'

export class HttpBuildingRepository implements BuildingRepository {
  private readonly apiClient: ApiClient
  private readonly branchRepository: BranchRepository

  constructor(apiClient: ApiClient, branchRepository: BranchRepository) {
    this.apiClient = apiClient
    this.branchRepository = branchRepository
  }

  private async buildBranchNameById(): Promise<Map<string, string>> {
    const branches = await this.branchRepository.list()
    return new Map(branches.map((branch) => [branch.id, branch.name]))
  }

  private toBuilding(buildingOut: BuildingOut, branchNameById: Map<string, string>): Building {
    return {
      id: buildingOut.id,
      branchId: buildingOut.branchId,
      branchName: branchNameById.get(buildingOut.branchId) ?? '',
      name: buildingOut.name,
      code: buildingOut.code,
      address: buildingOut.address ?? '',
      isActive: buildingOut.isActive,
    }
  }

  async list(): Promise<Building[]> {
    const [response, branchNameById] = await Promise.all([
      this.apiClient.makeRequest({
        endpointConfig: API_ENDPOINTS.LIST_BUILDINGS,
        queryParams: { pageSize: 100 },
        parserSchema: BuildingListResponseSchema,
      }),
      this.buildBranchNameById(),
    ])

    return response.data.map((buildingOut) => this.toBuilding(buildingOut, branchNameById))
  }

  async listPage({ page, pageSize, status, branchId }: ListBuildingsPageParams): Promise<BuildingsPage> {
    const [response, branchNameById] = await Promise.all([
      this.apiClient.makeRequest({
        endpointConfig: API_ENDPOINTS.LIST_BUILDINGS,
        queryParams: { page, pageSize, status },
        headers: branchId ? { 'X-Branch-ID': branchId } : undefined,
        parserSchema: BuildingListResponseSchema,
      }),
      this.buildBranchNameById(),
    ])

    return {
      items: response.data.map((buildingOut) => this.toBuilding(buildingOut, branchNameById)),
      total: response.pagination.total,
    }
  }

  async create(input: BuildingInput): Promise<Building> {
    const [response, branchNameById] = await Promise.all([
      this.apiClient.makeRequest({
        endpointConfig: API_ENDPOINTS.CREATE_BUILDING,
        body: {
          branchId: input.branchId,
          name: input.name,
          code: input.code,
          address: input.address,
          isActive: input.isActive,
        },
        parserSchema: BuildingResponseSchema,
      }),
      this.buildBranchNameById(),
    ])

    return this.toBuilding(response.data, branchNameById)
  }

  async update(id: string, input: BuildingInput): Promise<Building> {
    const [response, branchNameById] = await Promise.all([
      this.apiClient.makeRequest({
        endpointConfig: API_ENDPOINTS.UPDATE_BUILDING,
        body: {
          name: input.name,
          code: input.code,
          address: input.address,
          isActive: input.isActive,
        },
        pathParams: { id },
        parserSchema: BuildingResponseSchema,
      }),
      this.buildBranchNameById(),
    ])

    return this.toBuilding(response.data, branchNameById)
  }

  async remove(id: string): Promise<void> {
    await this.apiClient.makeRequest<unknown>({
      endpointConfig: API_ENDPOINTS.DELETE_BUILDING,
      pathParams: { id },
      parserSchema: z.unknown(),
    })
  }
}

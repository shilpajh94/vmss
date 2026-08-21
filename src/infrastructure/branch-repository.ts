import z from 'zod'
import { API_ENDPOINTS } from '../data/api/api-endpoints'
import type { ApiClient } from '../data/api/api-client'
import type { BranchRepository } from '../data/repositories/branch-repository'
import { BranchListResponseSchema, BranchResponseSchema, type BranchOut } from '../domain/entities/branch-out-schema'
import type { Branch } from '../domain/entities/branch-schema'

function toBranch(branchOut: BranchOut): Branch {
  return {
    id: branchOut.id,
    name: branchOut.name,
    code: branchOut.code,
    city: branchOut.city ?? '',
    country: branchOut.country ?? '',
    address: branchOut.address ?? '',
    contactPersonUserId: branchOut.contactPersonUserId ?? '',
    contactEmail: branchOut.contactEmail ?? '',
    contactPhone: branchOut.contactPhone ?? '',
    operatingHoursFrom: branchOut.operatingHoursFrom ?? undefined,
    operatingHoursTo: branchOut.operatingHoursTo ?? undefined,
    notes: branchOut.notes ?? undefined,
    isActive: branchOut.isActive,
  }
}

export class HttpBranchRepository implements BranchRepository {
  private readonly apiClient: ApiClient

  constructor(apiClient: ApiClient) {
    this.apiClient = apiClient
  }

  async list(): Promise<Branch[]> {
    const response = await this.apiClient.makeRequest({
      endpointConfig: API_ENDPOINTS.LIST_BRANCHES,
      queryParams: { pageSize: 100 },
      parserSchema: BranchListResponseSchema,
    })

    return response.data.map(toBranch)
  }

  async create(input: Omit<Branch, 'id'>): Promise<Branch> {
    const response = await this.apiClient.makeRequest({
      endpointConfig: API_ENDPOINTS.CREATE_BRANCH,
      body: input,
      parserSchema: BranchResponseSchema,
    })

    return toBranch(response.data)
  }

  async update(id: string, input: Omit<Branch, 'id'>): Promise<Branch> {
    const response = await this.apiClient.makeRequest({
      endpointConfig: API_ENDPOINTS.UPDATE_BRANCH,
      body: input,
      pathParams: { id },
      parserSchema: BranchResponseSchema,
    })

    return toBranch(response.data)
  }

  async remove(id: string): Promise<void> {
    await this.apiClient.makeRequest<unknown>({
      endpointConfig: API_ENDPOINTS.DELETE_BRANCH,
      pathParams: { id },
      parserSchema: z.unknown(),
    })
  }
}

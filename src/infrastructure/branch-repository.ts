import z from 'zod'
import { API_ENDPOINTS } from '../data/api/api-endpoints'
import type { ApiClient } from '../data/api/api-client'
import type { BranchRepository } from '../data/repositories/branch-repository'
import { BranchSchema, type Branch } from '../domain/entities/branch-schema'

export class HttpBranchRepository implements BranchRepository {
  private readonly apiClient: ApiClient

  constructor(apiClient: ApiClient) {
    this.apiClient = apiClient
  }

  async list(): Promise<Branch[]> {
    return this.apiClient.makeRequest<Branch[]>({
      endpointConfig: API_ENDPOINTS.LIST_BRANCHES,
      parserSchema: z.array(BranchSchema),
    })
  }

  async create(input: Omit<Branch, 'id'>): Promise<Branch> {
    return this.apiClient.makeRequest<Branch>({
      endpointConfig: API_ENDPOINTS.CREATE_BRANCH,
      body: input,
      parserSchema: BranchSchema,
    })
  }

  async update(id: string, input: Omit<Branch, 'id'>): Promise<Branch> {
    return this.apiClient.makeRequest<Branch>({
      endpointConfig: API_ENDPOINTS.UPDATE_BRANCH,
      body: input,
      queryParams: { id },
      parserSchema: BranchSchema,
    })
  }

  async remove(id: string): Promise<void> {
    await this.apiClient.makeRequest<unknown>({
      endpointConfig: API_ENDPOINTS.DELETE_BRANCH,
      queryParams: { id },
      parserSchema: z.unknown(),
    })
  }
}

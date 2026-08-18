import z from 'zod'
import { API_ENDPOINTS } from '../data/api/api-endpoints'
import type { ApiClient } from '../data/api/api-client'
import type { DepartmentRepository } from '../data/repositories/department-repository'
import { DepartmentSchema, type Department, type DepartmentInput } from '../domain/entities/department-schema'

export class HttpDepartmentRepository implements DepartmentRepository {
  private readonly apiClient: ApiClient

  constructor(apiClient: ApiClient) {
    this.apiClient = apiClient
  }

  async list(): Promise<Department[]> {
    return this.apiClient.makeRequest<Department[]>({
      endpointConfig: API_ENDPOINTS.LIST_DEPARTMENTS,
      parserSchema: z.array(DepartmentSchema),
    })
  }

  async create(input: DepartmentInput): Promise<Department> {
    return this.apiClient.makeRequest<Department>({
      endpointConfig: API_ENDPOINTS.CREATE_DEPARTMENT,
      body: input,
      parserSchema: DepartmentSchema,
    })
  }

  async update(id: string, input: DepartmentInput): Promise<Department> {
    return this.apiClient.makeRequest<Department>({
      endpointConfig: API_ENDPOINTS.UPDATE_DEPARTMENT,
      body: input,
      queryParams: { id },
      parserSchema: DepartmentSchema,
    })
  }

  async remove(id: string): Promise<void> {
    await this.apiClient.makeRequest<unknown>({
      endpointConfig: API_ENDPOINTS.DELETE_DEPARTMENT,
      queryParams: { id },
      parserSchema: z.unknown(),
    })
  }
}

import z from 'zod'
import { API_ENDPOINTS } from '../data/api/api-endpoints'
import type { ApiClient } from '../data/api/api-client'
import type { BranchRepository } from '../data/repositories/branch-repository'
import type { DepartmentRepository, DepartmentsPage, ListDepartmentsPageParams } from '../data/repositories/department-repository'
import { DepartmentListResponseSchema, DepartmentResponseSchema, type DepartmentOut } from '../domain/entities/department-out-schema'
import type { Department } from '../domain/entities/department-schema'

export class HttpDepartmentRepository implements DepartmentRepository {
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

  private toDepartment(departmentOut: DepartmentOut, branchNameById: Map<string, string>): Department {
    return {
      id: departmentOut.id,
      branchId: departmentOut.branchId,
      branchName: branchNameById.get(departmentOut.branchId) ?? '',
      floorId: departmentOut.floorId ?? undefined,
      name: departmentOut.name,
      code: departmentOut.code,
      isActive: departmentOut.isActive,
      headOfDepartmentUserId: departmentOut.headOfDepartmentUserId ?? undefined,
      description: departmentOut.description ?? undefined,
    }
  }

  async list(): Promise<Department[]> {
    const [response, branchNameById] = await Promise.all([
      this.apiClient.makeRequest({
        endpointConfig: API_ENDPOINTS.LIST_DEPARTMENTS,
        queryParams: { pageSize: 100 },
        parserSchema: DepartmentListResponseSchema,
      }),
      this.buildBranchNameById(),
    ])

    return response.data.map((departmentOut) => this.toDepartment(departmentOut, branchNameById))
  }

  async listPage({ page, pageSize, status, branchId }: ListDepartmentsPageParams): Promise<DepartmentsPage> {
    const [response, branchNameById] = await Promise.all([
      this.apiClient.makeRequest({
        endpointConfig: API_ENDPOINTS.LIST_DEPARTMENTS,
        queryParams: { page, pageSize, status },
        headers: branchId ? { 'X-Branch-ID': branchId } : undefined,
        parserSchema: DepartmentListResponseSchema,
      }),
      this.buildBranchNameById(),
    ])

    return {
      items: response.data.map((departmentOut) => this.toDepartment(departmentOut, branchNameById)),
      total: response.pagination.total,
    }
  }

  async create(input: Omit<Department, 'id' | 'branchName'>): Promise<Department> {
    const [response, branchNameById] = await Promise.all([
      this.apiClient.makeRequest({
        endpointConfig: API_ENDPOINTS.CREATE_DEPARTMENT,
        // DepartmentCreate has no isActive field — the backend defaults new departments to active.
        body: {
          branchId: input.branchId,
          floorId: input.floorId ?? null,
          name: input.name,
          code: input.code,
          headOfDepartmentUserId: input.headOfDepartmentUserId ?? null,
          description: input.description ?? null,
        },
        parserSchema: DepartmentResponseSchema,
      }),
      this.buildBranchNameById(),
    ])

    return this.toDepartment(response.data, branchNameById)
  }

  async update(id: string, input: Omit<Department, 'id' | 'branchName'>): Promise<Department> {
    const [response, branchNameById] = await Promise.all([
      this.apiClient.makeRequest({
        endpointConfig: API_ENDPOINTS.UPDATE_DEPARTMENT,
        body: {
          name: input.name,
          code: input.code,
          isActive: input.isActive,
          floorId: input.floorId ?? null,
          headOfDepartmentUserId: input.headOfDepartmentUserId ?? null,
          description: input.description ?? null,
        },
        pathParams: { id },
        parserSchema: DepartmentResponseSchema,
      }),
      this.buildBranchNameById(),
    ])

    return this.toDepartment(response.data, branchNameById)
  }

  async remove(id: string): Promise<void> {
    await this.apiClient.makeRequest<unknown>({
      endpointConfig: API_ENDPOINTS.DELETE_DEPARTMENT,
      pathParams: { id },
      parserSchema: z.unknown(),
    })
  }
}

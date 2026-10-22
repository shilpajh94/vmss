import { API_ENDPOINTS } from '../data/api/api-endpoints'
import type { ApiClient } from '../data/api/api-client'
import type { EmployeeDirectoryRepository } from '../data/repositories/employee-directory-repository'
import { EmployeeDirectoryListResponseSchema, type EmployeeDirectoryOut } from '../domain/entities/employee-directory-out-schema'
import type { EmployeeDirectoryEntry } from '../domain/entities/employee-directory-schema'
import { fetchAllPages } from '../data/api/fetch-all-pages'

function toEmployeeDirectoryEntry(employee: EmployeeDirectoryOut): EmployeeDirectoryEntry {
  return {
    id: employee.id,
    fullName: employee.fullName,
    designation: employee.designation ?? undefined,
    departmentId: employee.departmentId ?? undefined,
  }
}

export class HttpEmployeeDirectoryRepository implements EmployeeDirectoryRepository {
  private readonly apiClient: ApiClient

  constructor(apiClient: ApiClient) {
    this.apiClient = apiClient
  }

  async list(): Promise<EmployeeDirectoryEntry[]> {
    const entries = await fetchAllPages((page, pageSize) =>
      this.apiClient.makeRequest({
        endpointConfig: API_ENDPOINTS.LIST_EMPLOYEE_DIRECTORY,
        queryParams: { page, pageSize },
        parserSchema: EmployeeDirectoryListResponseSchema,
      }),
    )

    return entries.map(toEmployeeDirectoryEntry)
  }
}

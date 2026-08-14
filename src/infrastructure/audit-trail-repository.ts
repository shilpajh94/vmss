import { API_ENDPOINTS } from '../data/api/api-endpoints'
import type { ApiClient } from '../data/api/api-client'
import type { AuditTrailFilters, AuditTrailRepository } from '../data/repositories/audit-trail-repository'
import { AuditTrailResponseSchema, type AuditTrailResponse } from '../domain/entities/audit-trail-response-schema'

export class HttpAuditTrailRepository implements AuditTrailRepository {
  private readonly apiClient: ApiClient

  constructor(apiClient: ApiClient) {
    this.apiClient = apiClient
  }

  async list(filters: AuditTrailFilters): Promise<AuditTrailResponse> {
    return this.apiClient.makeRequest<AuditTrailResponse>({
      endpointConfig: API_ENDPOINTS.LIST_AUDIT_TRAIL,
      queryParams: {
        dateRange: filters.dateRange,
        activityType: filters.activityType,
        search: filters.search,
        page: filters.page,
        pageSize: filters.pageSize,
      },
      parserSchema: AuditTrailResponseSchema,
    })
  }
}

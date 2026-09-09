import { API_ENDPOINTS } from '../data/api/api-endpoints'
import type { ApiClient } from '../data/api/api-client'
import type { AuditReportFormat, AuditTrailFilters, AuditTrailRepository } from '../data/repositories/audit-trail-repository'
import { AuditTrailPaginatedResponseSchema, type AuditTrailResponse } from '../domain/entities/audit-trail-response-schema'
import { AuditReportJobResponseSchema, type AuditReportJob } from '../domain/entities/audit-report-job-schema'

const DATE_RANGE_TO_DAYS: Record<string, number> = {
  last_7_days: 7,
  last_30_days: 30,
  last_90_days: 90,
}

function resolveCreatedAfter(dateRange: string): string | undefined {
  const days = DATE_RANGE_TO_DAYS[dateRange]
  if (!days) return undefined

  const cutoff = new Date()
  cutoff.setDate(cutoff.getDate() - days)
  return cutoff.toISOString()
}

function resolveAction(activityType: string): string | undefined {
  return activityType === 'all' ? undefined : activityType
}

export class HttpAuditTrailRepository implements AuditTrailRepository {
  private readonly apiClient: ApiClient

  constructor(apiClient: ApiClient) {
    this.apiClient = apiClient
  }

  async list(filters: AuditTrailFilters): Promise<AuditTrailResponse> {
    const response = await this.apiClient.makeRequest({
      endpointConfig: API_ENDPOINTS.LIST_AUDIT_TRAIL,
      queryParams: {
        createdAfter: resolveCreatedAfter(filters.dateRange),
        action: resolveAction(filters.activityType),
        page: filters.page,
        pageSize: filters.pageSize,
      },
      parserSchema: AuditTrailPaginatedResponseSchema,
    })

    return { items: response.data, total: response.pagination.total }
  }

  async requestReport(filters: Pick<AuditTrailFilters, 'dateRange' | 'activityType'>, formats: AuditReportFormat[]): Promise<AuditReportJob> {
    const response = await this.apiClient.makeRequest({
      endpointConfig: API_ENDPOINTS.REQUEST_AUDIT_REPORT,
      body: {
        createdAfter: resolveCreatedAfter(filters.dateRange),
        action: resolveAction(filters.activityType),
        formats,
      },
      parserSchema: AuditReportJobResponseSchema,
    })

    return response.data
  }

  async getReport(jobId: string): Promise<AuditReportJob> {
    const response = await this.apiClient.makeRequest({
      endpointConfig: API_ENDPOINTS.GET_AUDIT_REPORT,
      pathParams: { jobId },
      parserSchema: AuditReportJobResponseSchema,
    })

    return response.data
  }

  // Report files require the bearer token, so they must be fetched here (not
  // opened via plain browser navigation, which sends no Authorization header)
  // and handed back as a Blob for the caller to save via an object URL.
  async downloadReport(jobId: string, format: AuditReportFormat): Promise<Blob> {
    return this.apiClient.downloadBlob({
      endpointConfig: API_ENDPOINTS.DOWNLOAD_AUDIT_REPORT,
      pathParams: { jobId },
      queryParams: { format },
    })
  }
}

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

    return this.resolveDownloadUrls(response.data)
  }

  async getReport(jobId: string): Promise<AuditReportJob> {
    const response = await this.apiClient.makeRequest({
      endpointConfig: API_ENDPOINTS.GET_AUDIT_REPORT,
      pathParams: { jobId },
      parserSchema: AuditReportJobResponseSchema,
    })

    return this.resolveDownloadUrls(response.data)
  }

  // The API currently returns download links as bare storage paths (e.g.
  // "var/storage/vmss/.../report.csv") rather than fetchable URLs — there is
  // no confirmed static-file route for them yet. This resolves them against
  // the API's origin as the most standard convention; revisit once the
  // backend confirms how these paths are meant to be served.
  private resolveDownloadUrls(job: AuditReportJob): AuditReportJob {
    const origin = new URL(this.apiClient.getBaseUrl(), window.location.origin).origin

    return {
      ...job,
      csvDownloadUrl: job.csvDownloadUrl ? `${origin}/${job.csvDownloadUrl}` : null,
      pdfDownloadUrl: job.pdfDownloadUrl ? `${origin}/${job.pdfDownloadUrl}` : null,
    }
  }
}

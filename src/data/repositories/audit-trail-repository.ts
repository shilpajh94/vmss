import type { AuditTrailResponse } from '../../domain/entities/audit-trail-response-schema'
import type { AuditReportJob } from '../../domain/entities/audit-report-job-schema'

export interface AuditTrailFilters {
  dateRange: string
  activityType: string
  page: number
  pageSize: number
}

export type AuditReportFormat = 'csv' | 'pdf'

export interface AuditTrailRepository {
  list(filters: AuditTrailFilters): Promise<AuditTrailResponse>
  requestReport(filters: Pick<AuditTrailFilters, 'dateRange' | 'activityType'>, formats: AuditReportFormat[]): Promise<AuditReportJob>
  getReport(jobId: string): Promise<AuditReportJob>
  downloadReport(jobId: string, format: AuditReportFormat): Promise<Blob>
}

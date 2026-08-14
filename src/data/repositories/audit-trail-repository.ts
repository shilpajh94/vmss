import type { AuditTrailResponse } from '../../domain/entities/audit-trail-response-schema'

export interface AuditTrailFilters {
  dateRange: string
  activityType: string
  search: string
  page: number
  pageSize: number
}

export interface AuditTrailRepository {
  list(filters: AuditTrailFilters): Promise<AuditTrailResponse>
}

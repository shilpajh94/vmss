import type { AuditReportFormat, AuditTrailFilters, AuditTrailRepository } from '../repositories/audit-trail-repository'
import type { AuditReportJob } from '../../domain/entities/audit-report-job-schema'

export class RequestAuditReportUseCase {
  private readonly auditTrailRepository: AuditTrailRepository

  constructor(auditTrailRepository: AuditTrailRepository) {
    this.auditTrailRepository = auditTrailRepository
  }

  async execute(filters: Pick<AuditTrailFilters, 'dateRange' | 'activityType'>, formats: AuditReportFormat[]): Promise<AuditReportJob> {
    return this.auditTrailRepository.requestReport(filters, formats)
  }
}

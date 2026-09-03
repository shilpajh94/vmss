import type { AuditTrailRepository } from '../repositories/audit-trail-repository'
import type { AuditReportJob } from '../../domain/entities/audit-report-job-schema'

export class GetAuditReportUseCase {
  private readonly auditTrailRepository: AuditTrailRepository

  constructor(auditTrailRepository: AuditTrailRepository) {
    this.auditTrailRepository = auditTrailRepository
  }

  async execute(jobId: string): Promise<AuditReportJob> {
    return this.auditTrailRepository.getReport(jobId)
  }
}

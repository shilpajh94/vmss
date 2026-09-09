import type { AuditReportFormat, AuditTrailRepository } from '../repositories/audit-trail-repository'

export class DownloadAuditReportUseCase {
  private readonly auditTrailRepository: AuditTrailRepository

  constructor(auditTrailRepository: AuditTrailRepository) {
    this.auditTrailRepository = auditTrailRepository
  }

  async execute(jobId: string, format: AuditReportFormat): Promise<Blob> {
    return this.auditTrailRepository.downloadReport(jobId, format)
  }
}

import type { AuditTrailFilters, AuditTrailRepository } from '../repositories/audit-trail-repository'
import type { AuditTrailResponse } from '../../domain/entities/audit-trail-response-schema'

export class GetAuditTrailUseCase {
  private readonly auditTrailRepository: AuditTrailRepository

  constructor(auditTrailRepository: AuditTrailRepository) {
    this.auditTrailRepository = auditTrailRepository
  }

  async execute(filters: AuditTrailFilters): Promise<AuditTrailResponse> {
    return this.auditTrailRepository.list(filters)
  }
}

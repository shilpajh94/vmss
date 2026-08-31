import type { VisitRequestSummary } from '../../domain/entities/visit-request-summary-schema'

export interface VisitRequestSummaryRepository {
  list(): Promise<VisitRequestSummary[]>
  approve(id: string): Promise<void>
}

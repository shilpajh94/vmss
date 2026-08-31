import type { VisitRequestSummary } from '../../domain/entities/visit-request-summary-schema'
import type { InvitationDetail } from '../../domain/entities/invitation-detail-schema'

export interface VisitRequestSummaryRepository {
  list(): Promise<VisitRequestSummary[]>
  approve(id: string): Promise<void>
  getDetail(id: string): Promise<InvitationDetail>
  reschedule(id: string, preferredVisitDate: string, preferredVisitTime: string): Promise<void>
  deny(id: string, reason: string): Promise<void>
  approveStep(invitationId: string, stepId: string): Promise<void>
  rejectStep(invitationId: string, stepId: string, reason: string): Promise<void>
}

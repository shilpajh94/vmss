import type { VisitRequestSummary } from '../../domain/entities/visit-request-summary-schema'
import type { InvitationDetail } from '../../domain/entities/invitation-detail-schema'

// Every field is optional — a PATCH sends only what changed. Deliberately
// excludes the visitor's personal fields, `visitorCategoryId`, and
// `hostId`/`hostNameOrEmail`: the API rejects any of those with a
// validation error (`extra="forbid"`), and reassigning the host stays
// exclusively the Delegate action's job.
export interface EditInvitationFields {
  purposeOfVisit?: string
  preferredVisitDate?: string
  preferredVisitTime?: string
  expectedDuration?: string
  departmentToVisit?: string
  additionalNotes?: string
}

export interface VisitRequestSummaryRepository {
  list(params?: { relevantToMe?: boolean }): Promise<VisitRequestSummary[]>
  approve(id: string): Promise<void>
  getDetail(id: string): Promise<InvitationDetail>
  reschedule(id: string, preferredVisitDate: string, preferredVisitTime: string): Promise<void>
  edit(id: string, fields: EditInvitationFields): Promise<void>
  deny(id: string, reason: string): Promise<void>
  approveStep(invitationId: string, stepId: string): Promise<void>
  rejectStep(invitationId: string, stepId: string, reason: string): Promise<void>
  delegateStep(invitationId: string, stepId: string, delegateUserId: string): Promise<void>
}

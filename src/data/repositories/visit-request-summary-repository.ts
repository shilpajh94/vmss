import type { VisitRequestSummary } from '../../domain/entities/visit-request-summary-schema'
import type { InvitationDetail } from '../../domain/entities/invitation-detail-schema'

// Every field is optional — a PATCH sends only what changed. Deliberately
// excludes the visitor's personal fields, `visitorCategoryId`, and
// `hostId`/`hostNameOrEmail`: confirmed live (2026-09-15) the API rejects
// any of those with "Extra inputs are not permitted" (`extra="forbid"`).
// Reassigning the host stays exclusively the Delegate action's job
// (`delegateStep`), which is the only endpoint that accepts it.
//
// `pocUserId` (Point of Contact) is a separate, independently-editable field
// from the host — confirmed live (2026-09-15) this endpoint accepts it and
// persists to `poc_user_id`/`poc_name`, and triggers the "you've been named
// point of contact" notification email.
export interface EditInvitationFields {
  purposeOfVisit?: string
  preferredVisitDate?: string
  preferredVisitTime?: string
  expectedDuration?: string
  departmentToVisit?: string
  additionalNotes?: string
  pocUserId?: string
}

export interface ListVisitRequestsParams {
  relevantToMe?: boolean
  status?: string
  registrationType?: string
  source?: string
  search?: string
  purposeOfVisit?: string
  page?: number
  pageSize?: number
}

export interface VisitRequestsPage {
  items: VisitRequestSummary[]
  total: number
}

export interface VisitRequestSummaryRepository {
  list(params?: ListVisitRequestsParams): Promise<VisitRequestsPage>
  approve(id: string): Promise<void>
  getDetail(id: string): Promise<InvitationDetail>
  reschedule(id: string, preferredVisitDate: string, preferredVisitTime: string): Promise<void>
  edit(id: string, fields: EditInvitationFields): Promise<void>
  deny(id: string, reason: string): Promise<void>
  checkOut(id: string, idempotencyKey: string): Promise<void>
  approveStep(invitationId: string, stepId: string): Promise<void>
  rejectStep(invitationId: string, stepId: string, reason: string): Promise<void>
  delegateStep(invitationId: string, stepId: string, delegateUserId: string): Promise<void>
}

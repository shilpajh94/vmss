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
  // ISO-8601 with a UTC offset. Only valid on `checked_out` visits (409
  // otherwise); the backend ignores every other field on such a visit.
  checkedOutAt?: string
}

// The dashboard drill-down filters (fix-dashboard-count-accuracy): with
// them a list holds exactly the invitations a dashboard figure counted.
// `visitDateFrom`/`visitDateTo` are YYYY-MM-DD visit days, inclusive.
export interface InvitationDrillDown {
  visitDateFrom?: string
  visitDateTo?: string
  upcoming?: boolean
  excludeExpired?: boolean
  branchId?: string
}

export interface ListVisitRequestsParams extends InvitationDrillDown {
  relevantToMe?: boolean
  status?: string
  registrationType?: string
  source?: string
  search?: string
  purposeOfVisit?: string
  page?: number
  pageSize?: number
  // `status_changed_at` orders by when each invitation entered its current
  // status; the API default is `submitted_at`.
  sortBy?: 'submitted_at' | 'created_at' | 'status_changed_at'
  sortOrder?: 'asc' | 'desc'
}

export type InvitationExportFormat = 'csv' | 'xlsx'

// `GET /invitations/export`: the list filters plus a status-matched date
// range (`dateFrom`/`dateTo` as YYYY-MM-DD, inclusive). The API returns one
// row per visitor; there's no pagination.
export interface InvitationExportParams extends InvitationDrillDown {
  format: InvitationExportFormat
  status?: string
  dateFrom?: string
  dateTo?: string
  relevantToMe?: boolean
  registrationType?: string
  source?: string
  search?: string
  purposeOfVisit?: string
}

export interface VisitRequestsPage {
  items: VisitRequestSummary[]
  total: number
}

export interface VisitRequestSummaryRepository {
  list(params?: ListVisitRequestsParams): Promise<VisitRequestsPage>
  export(params: InvitationExportParams): Promise<Blob>
  approve(id: string): Promise<void>
  getDetail(id: string): Promise<InvitationDetail>
  reschedule(id: string, preferredVisitDate: string, preferredVisitTime: string): Promise<void>
  edit(id: string, fields: EditInvitationFields): Promise<void>
  deny(id: string, reason: string): Promise<void>
  revertApproval(id: string, reason: string): Promise<void>
  checkOut(id: string, idempotencyKey: string): Promise<void>
  approveStep(invitationId: string, stepId: string): Promise<void>
  rejectStep(invitationId: string, stepId: string, reason: string): Promise<void>
  delegateStep(invitationId: string, stepId: string, delegateUserId: string): Promise<void>
}

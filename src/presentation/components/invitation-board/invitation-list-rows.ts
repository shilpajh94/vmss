import type { VisitRequestSummary } from '../../../domain/entities/visit-request-summary-schema'

// The slice of a board column the list needs.
interface ColumnLike {
  status: string
  label: string
  requests: ReadonlyArray<VisitRequestSummary>
}

export interface InvitationListRow {
  request: VisitRequestSummary
  // The board column the invitation sits in, so the list offers the same
  // actions the board does for that column.
  columnStatus: string
  statusLabel: string
}

// When the visit happens: its preferred date and time, else when it was
// submitted. Unparseable or absent values sort last.
function visitTimestamp(request: VisitRequestSummary): number {
  const { preferredVisitDate, preferredVisitTime, submittedAt } = request
  const visit = preferredVisitDate ? Date.parse(`${preferredVisitDate.slice(0, 10)}T${preferredVisitTime || '00:00'}`) : Number.NaN
  if (!Number.isNaN(visit)) return visit
  const submitted = submittedAt ? Date.parse(submittedAt) : Number.NaN
  return Number.isNaN(submitted) ? Number.NEGATIVE_INFINITY : submitted
}

// One list across the board's per-status columns, newest visit first. Only
// what each column has loaded is included.
export function flattenBoardColumns(columns: ReadonlyArray<ColumnLike>): InvitationListRow[] {
  return columns
    .flatMap((column) => column.requests.map((request) => ({ request, columnStatus: column.status, statusLabel: column.label })))
    .sort((a, b) => visitTimestamp(b.request) - visitTimestamp(a.request))
}

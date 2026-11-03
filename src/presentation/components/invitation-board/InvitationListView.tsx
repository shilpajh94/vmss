import { Avatar } from '../ui/Avatar'
import { EmptyState } from '../ui/EmptyState'
import { IconActionButton } from '../ui/IconActionButton'
import { CalendarClockIcon } from '../icons'
import { purposeLabel } from '../../utils/purpose-of-visit-options'
import type { ApprovalWorkflowRule } from '../../../domain/entities/approval-workflow-rule-schema'
import { deriveInvitationActions, type InvitationActionHandlers } from './invitation-actions'
import { flattenBoardColumns, type InvitationListRow } from './invitation-list-rows'
import type { VisitRequestSummary } from '../../../domain/entities/visit-request-summary-schema'

export interface InvitationListColumn {
  status: string
  label: string
  requests: ReadonlyArray<VisitRequestSummary>
  total: number
  hasMore: boolean
  isLoadingMore: boolean
  loadMoreFailed: boolean
  loadMore: () => void
}

// What the page allows for one board column's invitations; the same
// withholding rules the board applies when it builds each column.
export interface InvitationRowHandlers extends InvitationActionHandlers {
  onCheckOutClick?: (id: string) => void
}

interface InvitationListViewProps {
  columns: ReadonlyArray<InvitationListColumn>
  getHandlers: (columnStatus: string) => InvitationRowHandlers
  approvingId?: string
  workflowRulesByCategory?: Record<string, ApprovalWorkflowRule[]>
  isFiltering?: boolean
}

const STATUS_TONE_CLASSES: Record<string, string> = {
  submitted: 'bg-info/10 text-info',
  requested: 'bg-info/10 text-info',
  approved: 'bg-success/10 text-success-text',
  checked_in: 'bg-secondary-accent/10 text-secondary-accent',
  checked_out: 'bg-text-faint/15 text-text-muted',
  denied: 'bg-danger/10 text-danger',
  archived: 'bg-warning/10 text-warning',
}

// Full class names (not built strings) so Tailwind generates them.
const AVATAR_TINTS = ['bg-avatar-1', 'bg-avatar-2', 'bg-avatar-3', 'bg-avatar-4', 'bg-avatar-5', 'bg-avatar-6']

function avatarTintFor(trackingId: string): string {
  const hash = trackingId.split('').reduce((sum, char) => sum + char.charCodeAt(0), 0)
  return AVATAR_TINTS[hash % AVATAR_TINTS.length]
}

function visitSchedule(request: VisitRequestSummary): string {
  const parts = [request.preferredVisitDate?.slice(0, 10), request.preferredVisitTime].filter(Boolean)
  return parts.length > 0 ? parts.join(' · ') : '—'
}

function StatusChip({ request, label }: { request: VisitRequestSummary; label: string }) {
  return (
    <span
      className={`inline-flex w-fit rounded-full px-2.5 py-1 text-caption font-semibold whitespace-nowrap ${STATUS_TONE_CLASSES[request.status] ?? 'bg-neutral-subtle text-text-muted'}`}
    >
      {label}
    </span>
  )
}

function VisitorCell({ request, onOpen }: { request: VisitRequestSummary; onOpen?: (id: string) => void }) {
  return (
    <div className="flex min-w-0 items-center gap-3">
      <Avatar name={request.primaryContactFullName} size="lg" toneClassName={`text-ink ${avatarTintFor(request.trackingId)}`} />
      <div className="flex min-w-0 flex-col">
        {onOpen ? (
          <button
            type="button"
            onClick={() => onOpen(request.id)}
            aria-label={`Open visitor info for ${request.primaryContactFullName}, ${request.trackingId}`}
            className="truncate text-left font-body text-sm font-bold text-text hover:text-secondary-accent focus-visible:outline-none focus-visible:underline"
          >
            {request.primaryContactFullName}
          </button>
        ) : (
          <span className="truncate font-body text-sm font-bold text-text">{request.primaryContactFullName}</span>
        )}
        <span className="truncate font-body text-[11px] font-semibold text-text-faint">{request.trackingId}</span>
      </div>
    </div>
  )
}

function RowActions({
  row,
  handlers,
  isApproving,
  workflowRulesByCategory,
}: {
  row: InvitationListRow
  handlers: InvitationRowHandlers
  isApproving: boolean
  workflowRulesByCategory?: Record<string, ApprovalWorkflowRule[]>
}) {
  const { request } = row
  const { onCheckOutClick, ...actionHandlers } = handlers
  const { approveAction, canTapDeny, iconActions } = deriveInvitationActions(request, {
    ...actionHandlers,
    isDraggable: row.columnStatus === 'requested',
    isApproving,
    workflowRulesByCategory,
  })

  if (isApproving) {
    return (
      <p role="status" className="font-body text-[11px] text-text-faint">
        Approving…
      </p>
    )
  }

  return (
    <div className="flex flex-wrap items-center justify-end gap-1.5">
      {approveAction ? (
        <button
          type="button"
          onClick={approveAction.onClick}
          className="rounded-lg border border-success/40 bg-success/10 px-2.5 py-1.5 font-body text-[11px] font-semibold whitespace-nowrap text-success-text transition-colors hover:bg-success/15 max-lg:min-h-10"
        >
          {approveAction.label}
        </button>
      ) : null}
      {canTapDeny ? (
        <button
          type="button"
          onClick={() => handlers.onMoveToDenied?.(request.id)}
          className="rounded-lg border border-danger/40 bg-danger/10 px-2.5 py-1.5 font-body text-[11px] font-semibold text-danger transition-colors hover:bg-danger/15 max-lg:min-h-10"
        >
          Deny
        </button>
      ) : null}
      {onCheckOutClick ? (
        <button
          type="button"
          onClick={() => onCheckOutClick(request.id)}
          className="rounded-lg border border-secondary-accent/40 bg-secondary-accent/8 px-2.5 py-1.5 font-body text-[11px] font-semibold whitespace-nowrap text-secondary-accent transition-colors hover:bg-secondary-accent/15 max-lg:min-h-10"
        >
          Check Out
        </button>
      ) : null}
      {iconActions.map((action) => (
        <IconActionButton
          key={action.label}
          icon={action.icon}
          label={action.label}
          accessibleName={`${action.label} for ${request.trackingId}`}
          onClick={action.onClick}
        />
      ))}
    </div>
  )
}

/** The invitations as one table (stacked cards below `lg`), built from the
 * board's loaded columns so search, filters and actions are the board's. */
export function InvitationListView({ columns, getHandlers, approvingId, workflowRulesByCategory, isFiltering }: InvitationListViewProps) {
  const rows = flattenBoardColumns(columns)
  const loadedCount = rows.length
  const totalCount = columns.reduce((sum, column) => sum + column.total, 0)
  const moreColumns = columns.filter((column) => column.hasMore)

  if (rows.length === 0) {
    return (
      <EmptyState
        message={isFiltering ? 'No invitations match your filters' : 'No invitations yet'}
        icon={<CalendarClockIcon className="size-4 text-text-muted" />}
        className="rounded-2xl border border-border bg-surface p-12"
      />
    )
  }

  return (
    <div className="flex flex-col gap-3">
      {/* From `lg`: a table. */}
      <div className="hidden overflow-hidden rounded-2xl border border-border bg-surface lg:block">
        <table className="w-full text-left">
          <thead>
            <tr className="bg-border-subtle">
              {['Visitor', 'Status', 'Purpose', 'Visit', 'Type', 'Actions'].map((heading, index) => (
                <th
                  key={heading}
                  scope="col"
                  className={`px-5 py-3.5 font-body text-[13px] font-semibold text-text-muted ${index === 5 ? 'text-right' : ''}`}
                >
                  {heading}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => {
              const handlers = getHandlers(row.columnStatus)
              const { request } = row
              return (
                <tr key={request.id} className="border-t border-border-subtle transition-colors hover:bg-surface-inset">
                  <td className="max-w-[16rem] px-5 py-3">
                    <VisitorCell request={request} onOpen={handlers.onVisitorInfoClick} />
                  </td>
                  <td className="px-5 py-3">
                    <StatusChip request={request} label={row.statusLabel} />
                  </td>
                  <td className="max-w-[12rem] truncate px-5 py-3 font-body text-[13px] text-text-muted">
                    {purposeLabel(request.purposeOfVisit) ?? '—'}
                  </td>
                  <td className="px-5 py-3 font-body text-[13px] whitespace-nowrap text-text">{visitSchedule(request)}</td>
                  <td className="px-5 py-3 font-body text-[13px] whitespace-nowrap text-text-muted capitalize">{request.registrationType}</td>
                  <td className="px-5 py-3">
                    <RowActions
                      row={row}
                      handlers={handlers}
                      isApproving={approvingId === request.id}
                      workflowRulesByCategory={workflowRulesByCategory}
                    />
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>

      {/* Below `lg`: one card per invitation. */}
      <ul className="flex flex-col gap-2 lg:hidden">
        {rows.map((row) => {
          const handlers = getHandlers(row.columnStatus)
          const { request } = row
          return (
            <li key={request.id} className="flex flex-col gap-3 rounded-xl border border-border bg-surface p-3">
              <div className="flex items-start justify-between gap-2">
                <VisitorCell request={request} onOpen={handlers.onVisitorInfoClick} />
                <StatusChip request={request} label={row.statusLabel} />
              </div>
              <dl className="grid grid-cols-2 gap-x-3 gap-y-1 font-body text-[12px]">
                <dt className="text-text-faint">Purpose</dt>
                <dd className="truncate text-text">{purposeLabel(request.purposeOfVisit) ?? '—'}</dd>
                <dt className="text-text-faint">Visit</dt>
                <dd className="text-text">{visitSchedule(request)}</dd>
                <dt className="text-text-faint">Type</dt>
                <dd className="text-text capitalize">{request.registrationType}</dd>
              </dl>
              <RowActions
                row={row}
                handlers={handlers}
                isApproving={approvingId === request.id}
                workflowRulesByCategory={workflowRulesByCategory}
              />
            </li>
          )
        })}
      </ul>

      <div className="flex flex-wrap items-center justify-between gap-3">
        <p className="font-body text-[12px] text-text-muted">
          Showing {loadedCount} of {totalCount} invitations
        </p>
        <div className="flex flex-wrap gap-2">
          {moreColumns.map((column) => (
            <button
              key={column.status}
              type="button"
              disabled={column.isLoadingMore}
              onClick={column.loadMore}
              className="min-h-9 rounded-lg border border-border-subtle px-3 font-body text-[12px] font-semibold text-secondary-accent hover:bg-surface-inset disabled:opacity-60"
            >
              {column.isLoadingMore
                ? 'Loading…'
                : column.loadMoreFailed
                  ? `Retry ${column.label}`
                  : `Load more ${column.label.toLowerCase()} (${column.requests.length}/${column.total})`}
            </button>
          ))}
        </div>
      </div>
    </div>
  )
}

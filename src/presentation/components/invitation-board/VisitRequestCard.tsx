import type { VisitRequestSummary } from '../../../domain/entities/visit-request-summary-schema'
import type { InvitationDetail } from '../../../domain/entities/invitation-detail-schema'
import { resolveApproverLabel } from '../../utils/approval-step-label'
import { CalendarClockIcon } from '../icons'

const RESCHEDULABLE_STATUSES = new Set(['submitted', 'approved'])

const AVATAR_TINTS = ['#dbeafe', '#ffe4e6', '#d1fae5', '#fef3c7', '#f3e8ff', '#fee2e2']

function avatarTintFor(trackingId: string): string {
  const hash = trackingId.split('').reduce((sum, char) => sum + char.charCodeAt(0), 0)
  return AVATAR_TINTS[hash % AVATAR_TINTS.length]
}

function initialsFor(fullName: string): string {
  const parts = fullName.trim().split(/\s+/)
  return ((parts[0]?.[0] ?? '') + (parts[parts.length - 1]?.[0] ?? '')).toUpperCase()
}

interface VisitRequestCardProps {
  request: VisitRequestSummary
  isDraggable?: boolean
  isApproving?: boolean
  isExpanded?: boolean
  onToggleExpand?: (id: string) => void
  detail?: InvitationDetail
  isLoadingDetail?: boolean
  roleNameById?: Record<string, string>
  employeeNameById?: Record<string, string>
  onRescheduleClick?: (id: string) => void
  onDelegateClick?: (id: string) => void
  onVisitorInfoClick?: (id: string) => void
}

export function VisitRequestCard({
  request,
  isDraggable,
  isApproving,
  isExpanded,
  onToggleExpand,
  detail,
  isLoadingDetail,
  roleNameById,
  employeeNameById,
  onRescheduleClick,
  onDelegateClick,
  onVisitorInfoClick,
}: VisitRequestCardProps) {
  const canReschedule = Boolean(onRescheduleClick) && RESCHEDULABLE_STATUSES.has(request.status)
  const canDelegate = Boolean(onDelegateClick) && Boolean(detail?.currentApprovalStep)

  return (
    <div
      draggable={isDraggable && !isApproving}
      onDragStart={(event) => {
        event.dataTransfer.setData('text/plain', request.id)
        event.dataTransfer.effectAllowed = 'move'
      }}
      onClick={() => onToggleExpand?.(request.id)}
      className={`flex w-full flex-col gap-3 rounded-xl border border-border bg-surface p-4 drop-shadow-[0px_4px_4px_rgba(15,23,42,0.03)] ${
        isDraggable && !isApproving ? 'cursor-grab active:cursor-grabbing' : ''
      } ${isApproving ? 'opacity-60' : ''}`}
    >
      <div className="flex w-full items-center justify-between">
        <span
          className="flex size-8 shrink-0 items-center justify-center rounded-full font-display text-xs font-bold text-text"
          style={{ backgroundColor: avatarTintFor(request.trackingId) }}
        >
          {initialsFor(request.primaryContactFullName)}
        </span>
        <span className="font-body text-[11px] font-semibold whitespace-nowrap text-text-faint">{request.trackingId}</span>
      </div>

      <div className="flex w-full flex-col gap-1">
        <p className="truncate font-body text-sm font-bold text-text">{request.primaryContactFullName}</p>
        <div className="flex items-center gap-1 font-body text-xs">
          <span className="text-text-muted">Purpose:</span>
          <span className="font-medium text-text">{request.purposeOfVisit}</span>
        </div>
      </div>

      {detail?.currentApprovalStep ? (
        <div className="flex w-full items-center gap-1.5">
          <span className="flex shrink-0 items-center gap-1 rounded-full border border-info/30 bg-info/8 px-2 py-0.5 font-body text-[10px] font-bold whitespace-nowrap text-info">
            Level {detail.currentApprovalStep.stepOrder}/{detail.currentApprovalStep.totalSteps}
          </span>
          <span className="truncate font-body text-[10px] text-text-faint">
            Pending: {resolveApproverLabel(detail.currentApprovalStep, roleNameById, employeeNameById)}
          </span>
        </div>
      ) : null}

      {isExpanded ? (
        <div className="flex w-full items-center rounded-lg bg-bg px-2.5 py-1.5 font-body text-[11px] text-text-muted">
          {isLoadingDetail ? (
            <span>Loading approval progress…</span>
          ) : detail?.currentApprovalStep ? (
            <span>
              Step {detail.currentApprovalStep.stepOrder} of {detail.currentApprovalStep.totalSteps} — pending:{' '}
              {resolveApproverLabel(detail.currentApprovalStep, roleNameById, employeeNameById)}
            </span>
          ) : (
            <span>No multi-step approval workflow for this request.</span>
          )}
        </div>
      ) : null}

      {canReschedule || canDelegate || onVisitorInfoClick ? (
        <div className="flex w-full flex-wrap items-center gap-2" onClick={(event) => event.stopPropagation()}>
          {onVisitorInfoClick ? (
            <button
              type="button"
              onClick={() => onVisitorInfoClick(request.id)}
              className="min-w-[92px] flex-1 rounded-lg border border-border bg-surface px-2 py-1.5 font-body text-[11px] font-semibold whitespace-nowrap text-text transition-colors hover:border-secondary-accent/40 hover:bg-secondary-accent/8 hover:text-secondary-accent active:bg-secondary-accent/15"
            >
              Visitor Info
            </button>
          ) : null}
          {canReschedule ? (
            <button
              type="button"
              onClick={() => onRescheduleClick?.(request.id)}
              className="min-w-[92px] flex-1 rounded-lg border border-border bg-surface px-2 py-1.5 font-body text-[11px] font-semibold whitespace-nowrap text-text transition-colors hover:border-secondary-accent/40 hover:bg-secondary-accent/8 hover:text-secondary-accent active:bg-secondary-accent/15"
            >
              Reschedule
            </button>
          ) : null}
          {canDelegate ? (
            <button
              type="button"
              onClick={() => onDelegateClick?.(request.id)}
              className="min-w-[92px] flex-1 rounded-lg border border-border bg-surface px-2 py-1.5 font-body text-[11px] font-semibold whitespace-nowrap text-text transition-colors hover:border-secondary-accent/40 hover:bg-secondary-accent/8 hover:text-secondary-accent active:bg-secondary-accent/15"
            >
              Delegate
            </button>
          ) : null}
        </div>
      ) : null}

      {(request.preferredVisitDate && request.preferredVisitTime) || isApproving ? (
        <>
          <div className="h-px w-full bg-border-subtle" />

          <div className="flex w-full flex-col gap-1">
            {request.preferredVisitDate && request.preferredVisitTime ? (
              <div className="flex w-full items-center gap-1.5">
                <CalendarClockIcon className="size-3 shrink-0 text-text-faint" />
                <span className="font-body text-[11px] whitespace-nowrap text-text-faint">
                  Scheduled: {request.preferredVisitDate} {request.preferredVisitTime}
                </span>
              </div>
            ) : null}
            {isApproving ? (
              <div className="flex w-full items-center gap-1.5">
                <CalendarClockIcon className="size-3 shrink-0 text-text-faint" />
                <span className="font-body text-[11px] whitespace-nowrap text-text-faint">Approving…</span>
              </div>
            ) : null}
          </div>
        </>
      ) : null}
    </div>
  )
}

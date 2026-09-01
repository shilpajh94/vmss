import { useState } from 'react'
import type { VisitRequestSummary } from '../../../domain/entities/visit-request-summary-schema'
import type { InvitationDetail } from '../../../domain/entities/invitation-detail-schema'
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
  onReschedule?: (id: string, preferredVisitDate: string, preferredVisitTime: string) => void
  isRescheduling?: boolean
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
  onReschedule,
  isRescheduling,
}: VisitRequestCardProps) {
  const [rescheduleDate, setRescheduleDate] = useState('')
  const [rescheduleTime, setRescheduleTime] = useState('')
  const canReschedule = Boolean(onReschedule) && RESCHEDULABLE_STATUSES.has(request.status)

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

      {isExpanded ? (
        <div className="flex w-full items-center rounded-lg bg-bg px-2.5 py-1.5 font-body text-[11px] text-text-muted">
          {isLoadingDetail ? (
            <span>Loading approval progress…</span>
          ) : detail?.currentApprovalStep ? (
            <span>
              Step {detail.currentApprovalStep.stepOrder} of {detail.currentApprovalStep.totalSteps} — pending:{' '}
              {detail.currentApprovalStep.approverUserId
                ? (employeeNameById?.[detail.currentApprovalStep.approverUserId] ?? 'the invitation host')
                : (roleNameById?.[detail.currentApprovalStep.approverRoleId ?? ''] ?? 'the configured approver role')}
            </span>
          ) : (
            <span>No multi-step approval workflow for this request.</span>
          )}
        </div>
      ) : null}

      {isExpanded && canReschedule ? (
        <div
          className="flex w-full flex-col gap-2 rounded-lg bg-bg p-2.5"
          onClick={(event) => event.stopPropagation()}
        >
          <p className="font-body text-[11px] font-semibold text-text-muted">Reschedule visit</p>
          <div className="flex items-center gap-2">
            <input
              type="date"
              value={rescheduleDate}
              onChange={(event) => setRescheduleDate(event.target.value)}
              className="min-w-0 flex-1 rounded-md border border-border bg-surface px-2 py-1 font-body text-xs text-text"
            />
            <input
              type="time"
              value={rescheduleTime}
              onChange={(event) => setRescheduleTime(event.target.value)}
              className="min-w-0 flex-1 rounded-md border border-border bg-surface px-2 py-1 font-body text-xs text-text"
            />
          </div>
          <button
            type="button"
            disabled={!rescheduleDate || !rescheduleTime || isRescheduling}
            onClick={() => onReschedule?.(request.id, rescheduleDate, rescheduleTime)}
            className="w-full rounded-md bg-secondary-accent px-2 py-1.5 font-body text-xs font-semibold text-white disabled:opacity-50"
          >
            {isRescheduling ? 'Rescheduling…' : 'Save new date & time'}
          </button>
        </div>
      ) : null}

      <div className="h-px w-full bg-border-subtle" />

      <div className="flex w-full items-center gap-1.5">
        <CalendarClockIcon className="size-3 shrink-0 text-text-faint" />
        <span className="font-body text-[11px] whitespace-nowrap text-text-faint">
          {isApproving ? 'Approving…' : request.submittedAt}
        </span>
      </div>
    </div>
  )
}

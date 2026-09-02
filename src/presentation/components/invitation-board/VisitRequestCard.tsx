import { useState } from 'react'
import type { VisitRequestSummary } from '../../../domain/entities/visit-request-summary-schema'
import type { InvitationDetail } from '../../../domain/entities/invitation-detail-schema'
import type { HostEmployee } from '../../../domain/entities/host-employee-schema'
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
  onReschedule?: (id: string, preferredVisitDate: string, preferredVisitTime: string) => void
  isRescheduling?: boolean
  hostEmployees?: HostEmployee[]
  onDelegate?: (id: string, delegateUserId: string) => void
  isDelegating?: boolean
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
  hostEmployees,
  onDelegate,
  isDelegating,
}: VisitRequestCardProps) {
  const [rescheduleDate, setRescheduleDate] = useState('')
  const [rescheduleTime, setRescheduleTime] = useState('')
  const [delegateUserId, setDelegateUserId] = useState('')
  const canReschedule = Boolean(onReschedule) && RESCHEDULABLE_STATUSES.has(request.status)
  const canDelegate = Boolean(onDelegate) && Boolean(detail?.currentApprovalStep)
  // A step configured for a role can only be delegated to someone who holds
  // that role — the picker is locked to the step's own approverRoleId rather
  // than letting staff pick an unrelated role.
  const stepRoleId = detail?.currentApprovalStep?.approverRoleId
  const stepRoleName = stepRoleId ? roleNameById?.[stepRoleId] : undefined
  const delegateCandidates = stepRoleId
    ? hostEmployees?.filter((employee) => employee.branchRoles.some((branchRole) => branchRole.roleName === stepRoleName))
    : hostEmployees

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

      {isExpanded && canDelegate ? (
        <div
          className="flex w-full flex-col gap-2 rounded-lg bg-bg p-2.5"
          onClick={(event) => event.stopPropagation()}
        >
          <p className="font-body text-[11px] font-semibold text-text-muted">Delegate this step</p>
          {stepRoleId ? (
            <p className="font-body text-[11px] text-text-faint">
              Delegating within role: <span className="font-semibold text-text">{stepRoleName ?? 'the configured role'}</span>
            </p>
          ) : null}
          <select
            value={delegateUserId}
            onChange={(event) => setDelegateUserId(event.target.value)}
            className="w-full rounded-md border border-border bg-surface px-2 py-1 font-body text-xs text-text"
          >
            <option value="">
              {delegateCandidates?.length ? 'Select host…' : stepRoleId ? `No one currently holds ${stepRoleName}` : 'Select host…'}
            </option>
            {delegateCandidates?.map((employee) => (
              <option key={employee.id} value={employee.id}>
                {employee.fullName}
              </option>
            ))}
          </select>
          <button
            type="button"
            disabled={!delegateUserId || isDelegating}
            onClick={() => delegateUserId && onDelegate?.(request.id, delegateUserId)}
            className="w-full rounded-md bg-secondary-accent px-2 py-1.5 font-body text-xs font-semibold text-white disabled:opacity-50"
          >
            {isDelegating ? 'Delegating…' : 'Delegate approval'}
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

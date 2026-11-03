import { memo } from 'react'
import { Avatar } from '../ui/Avatar'
import type { VisitRequestSummary } from '../../../domain/entities/visit-request-summary-schema'
import {
  resolveApproverLabel,
  resolveCurrentLevel,
  resolveNextStepPreviewLabel,
  resolveTotalSteps,
} from '../../utils/approval-step-label'
import type { ApprovalWorkflowRule } from '../../../domain/entities/approval-workflow-rule-schema'
import { CalendarClockIcon } from '../icons'
import { deriveInvitationActions } from './invitation-actions'
import { IconActionButton } from '../ui/IconActionButton'
import { purposeLabel } from '../../utils/purpose-of-visit-options'

// Full class names (not built strings) so Tailwind generates them.
const AVATAR_TINTS = ['bg-avatar-1', 'bg-avatar-2', 'bg-avatar-3', 'bg-avatar-4', 'bg-avatar-5', 'bg-avatar-6']

function avatarTintFor(trackingId: string): string {
  const hash = trackingId.split('').reduce((sum, char) => sum + char.charCodeAt(0), 0)
  return AVATAR_TINTS[hash % AVATAR_TINTS.length]
}

interface VisitRequestCardProps {
  request: VisitRequestSummary
  isDraggable?: boolean
  isApproving?: boolean
  roleNameById?: Record<string, string>
  employeeNameById?: Record<string, string>
  workflowRulesByCategory?: Record<string, ApprovalWorkflowRule[]>
  onRescheduleClick?: (id: string) => void
  onDelegateClick?: (id: string) => void
  onApproveAndDelegateClick?: (id: string) => void
  onApproveClick?: (id: string) => void
  onEditClick?: (id: string) => void
  // Checked-out cards only get Edit (for the check-out time) when true.
  canEditCheckOutTime?: boolean
  onVisitorInfoClick?: (id: string) => void
  // Only passed to Checked-in cards, and only for staff who may check out.
  onCheckOutClick?: (id: string) => void
  // Shown on Approved cards only (add-invitation-approval-revert).
  onRevertClick?: (id: string) => void
  // Approve/Deny buttons (cards are no longer draggable). Shown at every size,
  // and only when the card is actionable (`isDraggable`).
  onMoveToApproved?: (id: string) => void
  onMoveToDenied?: (id: string) => void
}

// Memoised: a board re-renders on every poll, filter keystroke and dialog
// toggle, and most cards' props (the row, the hook's stable callbacks, the
// memoised name maps) haven't changed.
export const VisitRequestCard = memo(function VisitRequestCard({
  request,
  isDraggable,
  isApproving,
  roleNameById,
  employeeNameById,
  workflowRulesByCategory,
  onRescheduleClick,
  onDelegateClick,
  onApproveAndDelegateClick,
  onApproveClick,
  onEditClick,
  canEditCheckOutTime,
  onVisitorInfoClick,
  onCheckOutClick,
  onRevertClick,
  onMoveToApproved,
  onMoveToDenied,
}: VisitRequestCardProps) {
  // The list item carries the approval step (design D12), so a card never
  // needs its own detail request.
  const progress = request
  const pendingApproverLabel = progress.currentApprovalStep
    ? (resolveNextStepPreviewLabel(progress, workflowRulesByCategory ?? {}, roleNameById ?? {}) ??
      resolveApproverLabel(progress.currentApprovalStep, roleNameById, employeeNameById))
    : undefined
  const totalSteps = progress.currentApprovalStep ? resolveTotalSteps(progress, workflowRulesByCategory ?? {}) : undefined
  const { approveAction, canTapDeny, iconActions } = deriveInvitationActions(request, {
    isDraggable,
    isApproving,
    workflowRulesByCategory,
    onRescheduleClick,
    onDelegateClick,
    onApproveAndDelegateClick,
    onApproveClick,
    onEditClick,
    canEditCheckOutTime,
    onVisitorInfoClick,
    onRevertClick,
    onMoveToApproved,
    onMoveToDenied,
  })
  const hasPrimaryActions = Boolean(approveAction) || canTapDeny || Boolean(onCheckOutClick)

  // The list item doesn't carry the host; Visitor Info shows it.
  const metaLine = purposeLabel(request.purposeOfVisit) ?? 'No purpose given'
  const hasSchedule = Boolean(request.preferredVisitDate && request.preferredVisitTime)

  return (
    // The visitor's name is the one control that opens Visitor Info; its
    // `::after` stretches over the card so a click anywhere still opens it,
    // while the action buttons sit above that overlay as separate controls
    // (accessibility "Interactive Elements Are Not Nested").
    <article
      aria-label={`${request.primaryContactFullName}, ${request.trackingId}`}
      className={`relative flex w-full flex-col gap-2 rounded-xl border border-border bg-surface p-3 drop-shadow-[0px_4px_4px_rgba(15,23,42,0.03)] ${
        onVisitorInfoClick ? 'cursor-pointer transition-colors hover:border-secondary-accent/40' : ''
      } ${isApproving ? 'opacity-60' : ''}`}
    >
      <div className="flex w-full items-center gap-2.5">
        <Avatar
          name={request.primaryContactFullName}
          size="md"
          toneClassName={`text-ink ${avatarTintFor(request.trackingId)}`}
        />
        <div className="flex min-w-0 flex-1 flex-col">
          {onVisitorInfoClick ? (
            <button
              type="button"
              onClick={() => onVisitorInfoClick(request.id)}
              aria-label={`Open visitor info for ${request.primaryContactFullName}, ${request.trackingId}`}
              className="truncate text-left font-body text-sm font-bold text-text after:absolute after:inset-0 after:rounded-xl after:content-[''] focus-visible:outline-none focus-visible:after:ring-2 focus-visible:after:ring-secondary-accent"
            >
              {request.primaryContactFullName}
            </button>
          ) : (
            <p className="truncate font-body text-sm font-bold text-text">{request.primaryContactFullName}</p>
          )}
          <span className="truncate font-body text-[11px] font-semibold text-text-faint">{request.trackingId}</span>
        </div>
      </div>

      <div className="flex w-full flex-col gap-1">
        <p title={metaLine} className="truncate font-body text-xs font-medium text-text-muted">
          {metaLine}
        </p>
        {hasSchedule ? (
          <div className="flex w-full items-center gap-1.5">
            <CalendarClockIcon className="size-3 shrink-0 text-text-faint" />
            <span className="truncate font-body text-[11px] text-text-faint">
              {request.preferredVisitDate} {request.preferredVisitTime}
            </span>
          </div>
        ) : null}
      </div>

      {progress.currentApprovalStep ? (
        <div className="flex w-full items-center gap-1.5">
          <span className="flex shrink-0 items-center gap-1 rounded-full border border-info/30 bg-info/8 px-2 py-0.5 font-body text-[10px] font-bold whitespace-nowrap text-info">
            Level {resolveCurrentLevel(progress.currentApprovalStep, progress.visitorCategoryId, workflowRulesByCategory ?? {})}/{totalSteps}
          </span>
          <span className="truncate font-body text-[10px] text-text-faint">Pending: {pendingApproverLabel}</span>
        </div>
      ) : null}

      {isApproving ? (
        <p role="status" className="font-body text-[11px] text-text-faint">
          Approving…
        </p>
      ) : hasPrimaryActions ? (
        <div className="relative z-10 grid w-full grid-cols-2 gap-2">
          {approveAction ? (
            <button
              type="button"
              onClick={approveAction.onClick}
              className={`truncate rounded-lg border border-success/40 bg-success/10 px-2 py-1.5 font-body text-[11px] font-semibold text-success-text transition-colors hover:bg-success/15 max-lg:min-h-10 max-lg:text-xs ${
                canTapDeny ? '' : 'col-span-full'
              }`}
            >
              {approveAction.label}
            </button>
          ) : null}
          {canTapDeny ? (
            <button
              type="button"
              onClick={() => onMoveToDenied?.(request.id)}
              className={`truncate rounded-lg border border-danger/40 bg-danger/10 px-2 py-1.5 font-body text-[11px] font-semibold text-danger transition-colors hover:bg-danger/15 max-lg:min-h-10 max-lg:text-xs ${
                approveAction ? '' : 'col-span-full'
              }`}
            >
              Deny
            </button>
          ) : null}
          {onCheckOutClick ? (
            <button
              type="button"
              onClick={() => onCheckOutClick(request.id)}
              className="col-span-full rounded-lg border border-secondary-accent/40 bg-secondary-accent/8 px-2 py-1.5 font-body text-[11px] font-semibold text-secondary-accent transition-colors hover:bg-secondary-accent/15 active:bg-secondary-accent/20 max-lg:min-h-10 max-lg:text-xs"
            >
              Check Out
            </button>
          ) : null}
        </div>
      ) : null}

      {iconActions.length > 0 ? (
        <div className="relative z-10 -mx-1 -mb-1 flex w-full flex-wrap items-center gap-1">
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
      ) : null}
    </article>
  )
})

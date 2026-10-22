import { memo } from 'react'
import { Avatar } from '../ui/Avatar'
import type { VisitRequestSummary } from '../../../domain/entities/visit-request-summary-schema'
import {
  isReceptionCurrentStep,
  resolveApproverLabel,
  resolveCurrentLevel,
  resolveNextStepPreviewLabel,
  resolveTotalSteps,
} from '../../utils/approval-step-label'
import type { ApprovalWorkflowRule } from '../../../domain/entities/approval-workflow-rule-schema'
import { CalendarClockIcon, InfoIcon, PencilIcon, UndoIcon, UserCheckIcon } from '../icons'
import { IconActionButton } from '../ui/IconActionButton'
import { purposeLabel } from '../../utils/purpose-of-visit-options'

// An archived no-show can be rescheduled or edited; the API sends it back for
// re-approval when its date changes.
const RESCHEDULABLE_STATUSES = new Set(['submitted', 'approved', 'archived'])

const AVATAR_TINTS = ['#dbeafe', '#ffe4e6', '#d1fae5', '#fef3c7', '#f3e8ff', '#fee2e2']

function avatarTintFor(trackingId: string): string {
  const hash = trackingId.split('').reduce((sum, char) => sum + char.charCodeAt(0), 0)
  return AVATAR_TINTS[hash % AVATAR_TINTS.length]
}

interface IconAction {
  label: string
  icon: typeof InfoIcon
  onClick: () => void
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
  onVisitorInfoClick,
  onCheckOutClick,
  onRevertClick,
  onMoveToApproved,
  onMoveToDenied,
}: VisitRequestCardProps) {
  // The list item carries the approval step (design D12), so a card never
  // needs its own detail request.
  const progress = request
  const isReceptionStep = isReceptionCurrentStep(progress.currentApprovalStep, progress.visitorCategoryId, workflowRulesByCategory ?? {})
  const pendingApproverLabel = progress.currentApprovalStep
    ? (resolveNextStepPreviewLabel(progress, workflowRulesByCategory ?? {}, roleNameById ?? {}) ??
      resolveApproverLabel(progress.currentApprovalStep, roleNameById, employeeNameById))
    : undefined
  const totalSteps = progress.currentApprovalStep ? resolveTotalSteps(progress, workflowRulesByCategory ?? {}) : undefined
  const canReschedule = Boolean(onRescheduleClick) && RESCHEDULABLE_STATUSES.has(request.status)
  const canDelegate = Boolean(onDelegateClick) && Boolean(progress.currentApprovalStep) && !isReceptionStep
  // Reception never uses drag-and-drop to approve — it always acts through an
  // explicit button, either "Approve & Delegate" (another level follows) or
  // plain "Approve" (Reception is the only/last level), so the outcome is
  // deliberate rather than an accidental card drag.
  const isReceptionApprovalStep = isReceptionStep && Boolean(progress.currentApprovalStep)
  const isLockedToApproveAndDelegate = isReceptionApprovalStep && (totalSteps ?? 0) > 1
  const canApproveAndDelegate = Boolean(onApproveAndDelegateClick) && isLockedToApproveAndDelegate
  const canApprove = Boolean(onApproveClick) && isReceptionApprovalStep && (totalSteps ?? 0) <= 1
  const canEdit = Boolean(onEditClick) && RESCHEDULABLE_STATUSES.has(request.status)
  const canRevert = Boolean(onRevertClick) && request.status === 'approved'
  // Until the category's live workflow rules have loaded,
  // `isReceptionStep`/`totalSteps` fall back to the step's own possibly-stale
  // `stepOrder`/`totalSteps` snapshot, which can misidentify Reception's step
  // as a later, freely-draggable one (`approve()` still hard-blocks this
  // case regardless — this just avoids the card visibly allowing a drag that
  // would immediately be rejected).
  const workflowRulesLoaded =
    !progress.currentApprovalStep || !progress.visitorCategoryId || workflowRulesByCategory?.[progress.visitorCategoryId] !== undefined
  const isActionable = isDraggable && !isApproving && workflowRulesLoaded
  // Reception's own step approves through its dedicated buttons, but it can
  // still deny.
  const canTapApprove = isActionable && !isReceptionApprovalStep && Boolean(onMoveToApproved)
  const canTapDeny = isActionable && Boolean(onMoveToDenied)


  // Only the actions that decide the request's next state are labelled
  // buttons; the rest are a compact icon row so cards stay short.
  const approveAction = canApproveAndDelegate
    ? { label: 'Approve & Delegate', onClick: () => onApproveAndDelegateClick?.(request.id) }
    : canApprove
      ? { label: 'Approve', onClick: () => onApproveClick?.(request.id) }
      : canTapApprove
        ? { label: 'Approve', onClick: () => onMoveToApproved?.(request.id) }
        : undefined
  const hasPrimaryActions = Boolean(approveAction) || canTapDeny || Boolean(onCheckOutClick)

  const iconActions = [
    onVisitorInfoClick && { label: 'Visitor info', icon: InfoIcon, onClick: () => onVisitorInfoClick(request.id) },
    canReschedule && { label: 'Reschedule', icon: CalendarClockIcon, onClick: () => onRescheduleClick?.(request.id) },
    canEdit && { label: 'Edit', icon: PencilIcon, onClick: () => onEditClick?.(request.id) },
    canDelegate && { label: 'Delegate', icon: UserCheckIcon, onClick: () => onDelegateClick?.(request.id) },
    canRevert && { label: 'Revert approval', icon: UndoIcon, onClick: () => onRevertClick?.(request.id) },
  ].filter((action): action is IconAction => Boolean(action))

  // The list item doesn't carry the host; Visitor Info shows it.
  const metaLine = purposeLabel(request.purposeOfVisit) ?? 'No purpose given'
  const hasSchedule = Boolean(request.preferredVisitDate && request.preferredVisitTime)

  return (
    <div
      role={onVisitorInfoClick ? 'button' : undefined}
      tabIndex={onVisitorInfoClick ? 0 : undefined}
      aria-label={onVisitorInfoClick ? `Open visitor info for ${request.primaryContactFullName}, ${request.trackingId}` : undefined}
      onClick={() => onVisitorInfoClick?.(request.id)}
      onKeyDown={(event) => {
        // Only the card itself — keys pressed on its buttons or menu items
        // bubble up here too and must not also open Visitor Info.
        if (event.target !== event.currentTarget || !onVisitorInfoClick) return
        if (event.key === 'Enter' || event.key === ' ') {
          event.preventDefault()
          onVisitorInfoClick(request.id)
        }
      }}
      className={`relative flex w-full flex-col gap-2 rounded-xl border border-border bg-surface p-3 drop-shadow-[0px_4px_4px_rgba(15,23,42,0.03)] ${
        onVisitorInfoClick
          ? 'cursor-pointer transition-colors hover:border-secondary-accent/40 focus-visible:ring-2 focus-visible:ring-secondary-accent/40 focus-visible:outline-none'
          : ''
      } ${isApproving ? 'opacity-60' : ''}`}
    >
      <div className="flex w-full items-center gap-2.5">
        <Avatar
          name={request.primaryContactFullName}
          size="md"
          toneClassName="text-ink"
          style={{ backgroundColor: avatarTintFor(request.trackingId) }}
        />
        <div className="flex min-w-0 flex-1 flex-col">
          <p className="truncate font-body text-sm font-bold text-text">{request.primaryContactFullName}</p>
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
        <div className="grid w-full grid-cols-2 gap-2" onClick={(event) => event.stopPropagation()}>
          {approveAction ? (
            <button
              type="button"
              onClick={approveAction.onClick}
              className={`truncate rounded-lg border border-success/40 bg-success/10 px-2 py-1.5 font-body text-[11px] font-semibold text-success transition-colors hover:bg-success/15 max-lg:min-h-10 max-lg:text-xs ${
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
        <div className="-mx-1 -mb-1 flex w-full items-center gap-1" onClick={(event) => event.stopPropagation()}>
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
    </div>
  )
})

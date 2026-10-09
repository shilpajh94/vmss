import type { VisitRequestSummary } from '../../../domain/entities/visit-request-summary-schema'
import type { InvitationDetail } from '../../../domain/entities/invitation-detail-schema'
import {
  isReceptionCurrentStep,
  resolveApproverLabel,
  resolveCurrentLevel,
  resolveNextStepPreviewLabel,
  resolveTotalSteps,
} from '../../utils/approval-step-label'
import type { ApprovalWorkflowRule } from '../../../domain/entities/approval-workflow-rule-schema'
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
  workflowRulesByCategory?: Record<string, ApprovalWorkflowRule[]>
  onRescheduleClick?: (id: string) => void
  onDelegateClick?: (id: string) => void
  onApproveAndDelegateClick?: (id: string) => void
  onApproveClick?: (id: string) => void
  onEditClick?: (id: string) => void
  onVisitorInfoClick?: (id: string) => void
  // Approve/Deny buttons (cards are no longer draggable). Shown at every size,
  // and only when the card is actionable (`isDraggable`).
  onMoveToApproved?: (id: string) => void
  onMoveToDenied?: (id: string) => void
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
  workflowRulesByCategory,
  onRescheduleClick,
  onDelegateClick,
  onApproveAndDelegateClick,
  onApproveClick,
  onEditClick,
  onVisitorInfoClick,
  onMoveToApproved,
  onMoveToDenied,
}: VisitRequestCardProps) {
  const isReceptionStep = isReceptionCurrentStep(detail?.currentApprovalStep, detail?.visitorCategoryId, workflowRulesByCategory ?? {})
  const pendingApproverLabel = detail?.currentApprovalStep
    ? (resolveNextStepPreviewLabel(detail, workflowRulesByCategory ?? {}, roleNameById ?? {}) ??
      resolveApproverLabel(detail.currentApprovalStep, roleNameById, employeeNameById))
    : undefined
  const totalSteps = detail?.currentApprovalStep ? resolveTotalSteps(detail, workflowRulesByCategory ?? {}) : undefined
  const canReschedule = Boolean(onRescheduleClick) && RESCHEDULABLE_STATUSES.has(request.status)
  const canDelegate = Boolean(onDelegateClick) && Boolean(detail?.currentApprovalStep) && !isReceptionStep
  // Reception never uses drag-and-drop to approve — it always acts through an
  // explicit button, either "Approve & Delegate" (another level follows) or
  // plain "Approve" (Reception is the only/last level), so the outcome is
  // deliberate rather than an accidental card drag.
  const isReceptionApprovalStep = isReceptionStep && Boolean(detail?.currentApprovalStep)
  const isLockedToApproveAndDelegate = isReceptionApprovalStep && (totalSteps ?? 0) > 1
  const canApproveAndDelegate = Boolean(onApproveAndDelegateClick) && isLockedToApproveAndDelegate
  const canApprove = Boolean(onApproveClick) && isReceptionApprovalStep && (totalSteps ?? 0) <= 1
  const canEdit = Boolean(onEditClick) && RESCHEDULABLE_STATUSES.has(request.status)
  // Before this card's detail has loaded, we don't yet know whether it's
  // Reception's own step — default to not draggable rather than briefly
  // allowing a drag that would then be blocked once the detail arrives.
  // Same for the category's live workflow rules: until they've loaded,
  // `isReceptionStep`/`totalSteps` fall back to the step's own possibly-stale
  // `stepOrder`/`totalSteps` snapshot, which can misidentify Reception's step
  // as a later, freely-draggable one (`approve()` still hard-blocks this
  // case regardless — this just avoids the card visibly allowing a drag that
  // would immediately be rejected).
  const workflowRulesLoaded =
    !detail?.currentApprovalStep || !detail.visitorCategoryId || workflowRulesByCategory?.[detail.visitorCategoryId] !== undefined
  const isActionable = isDraggable && !isApproving && detail !== undefined && workflowRulesLoaded
  // Reception's own step approves through its dedicated buttons, but it can
  // still deny.
  const canTapApprove = isActionable && !isReceptionApprovalStep && Boolean(onMoveToApproved)
  const canTapDeny = isActionable && Boolean(onMoveToDenied)

  return (
    <div
      onClick={() => onToggleExpand?.(request.id)}
      className={`flex w-full flex-col gap-3 rounded-xl border border-border bg-surface p-4 drop-shadow-[0px_4px_4px_rgba(15,23,42,0.03)] ${isApproving ? 'opacity-60' : ''}`}
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
        {detail ? (
          <div className="flex items-center gap-1 font-body text-xs">
            <span className="text-text-muted">Host:</span>
            <span className="font-medium text-text">{detail.hostNameOrEmail ?? 'Unassigned — Front Office'}</span>
          </div>
        ) : null}
      </div>

      {detail?.currentApprovalStep ? (
        <div className="flex w-full items-center gap-1.5">
          <span className="flex shrink-0 items-center gap-1 rounded-full border border-info/30 bg-info/8 px-2 py-0.5 font-body text-[10px] font-bold whitespace-nowrap text-info">
            Level {resolveCurrentLevel(detail.currentApprovalStep, detail.visitorCategoryId, workflowRulesByCategory ?? {})}/{totalSteps}
          </span>
          <span className="truncate font-body text-[10px] text-text-faint">Pending: {pendingApproverLabel}</span>
        </div>
      ) : null}

      {isExpanded ? (
        <div className="flex w-full items-center rounded-lg bg-bg px-2.5 py-1.5 font-body text-[11px] text-text-muted">
          {isLoadingDetail ? (
            <span>Loading approval progress…</span>
          ) : detail?.currentApprovalStep ? (
            <span>
              Step {resolveCurrentLevel(detail.currentApprovalStep, detail.visitorCategoryId, workflowRulesByCategory ?? {})} of {totalSteps} —
              pending: {pendingApproverLabel}
            </span>
          ) : (
            <span>No multi-step approval workflow for this request.</span>
          )}
        </div>
      ) : null}

      {canReschedule || canDelegate || canApproveAndDelegate || canApprove || canEdit || canTapApprove || canTapDeny || onVisitorInfoClick ? (
        <div className="flex w-full flex-wrap items-center gap-2" onClick={(event) => event.stopPropagation()}>
          {onVisitorInfoClick ? (
            <button
              type="button"
              onClick={() => onVisitorInfoClick(request.id)}
              className="min-w-[92px] flex-1 rounded-lg border border-border bg-surface px-2 py-1.5 font-body text-[11px] font-semibold max-lg:py-2.5 max-lg:text-xs whitespace-nowrap text-text transition-colors hover:border-secondary-accent/40 hover:bg-secondary-accent/8 hover:text-secondary-accent active:bg-secondary-accent/15"
            >
              Visitor Info
            </button>
          ) : null}
          {canReschedule ? (
            <button
              type="button"
              onClick={() => onRescheduleClick?.(request.id)}
              className="min-w-[92px] flex-1 rounded-lg border border-border bg-surface px-2 py-1.5 font-body text-[11px] font-semibold max-lg:py-2.5 max-lg:text-xs whitespace-nowrap text-text transition-colors hover:border-secondary-accent/40 hover:bg-secondary-accent/8 hover:text-secondary-accent active:bg-secondary-accent/15"
            >
              Reschedule
            </button>
          ) : null}
          {canDelegate ? (
            <button
              type="button"
              onClick={() => onDelegateClick?.(request.id)}
              className="min-w-[92px] flex-1 rounded-lg border border-border bg-surface px-2 py-1.5 font-body text-[11px] font-semibold max-lg:py-2.5 max-lg:text-xs whitespace-nowrap text-text transition-colors hover:border-secondary-accent/40 hover:bg-secondary-accent/8 hover:text-secondary-accent active:bg-secondary-accent/15"
            >
              Delegate
            </button>
          ) : null}
          {canApproveAndDelegate ? (
            <button
              type="button"
              onClick={() => onApproveAndDelegateClick?.(request.id)}
              className="min-w-[92px] flex-1 rounded-lg border border-border bg-surface px-2 py-1.5 font-body text-[11px] font-semibold max-lg:py-2.5 max-lg:text-xs whitespace-nowrap text-text transition-colors hover:border-secondary-accent/40 hover:bg-secondary-accent/8 hover:text-secondary-accent active:bg-secondary-accent/15"
            >
              Approve &amp; Delegate
            </button>
          ) : null}
          {canApprove ? (
            <button
              type="button"
              onClick={() => onApproveClick?.(request.id)}
              className="min-w-[92px] flex-1 rounded-lg border border-border bg-surface px-2 py-1.5 font-body text-[11px] font-semibold max-lg:py-2.5 max-lg:text-xs whitespace-nowrap text-text transition-colors hover:border-secondary-accent/40 hover:bg-secondary-accent/8 hover:text-secondary-accent active:bg-secondary-accent/15"
            >
              Approve
            </button>
          ) : null}
          {canTapApprove ? (
            <button
              type="button"
              onClick={() => onMoveToApproved?.(request.id)}
              className="min-w-[92px] flex-1 rounded-lg border border-success/40 bg-success/10 px-2 py-1.5 font-body text-[11px] font-semibold whitespace-nowrap text-success max-lg:py-2.5 max-lg:text-xs"
            >
              Approve
            </button>
          ) : null}
          {canTapDeny ? (
            <button
              type="button"
              onClick={() => onMoveToDenied?.(request.id)}
              className="min-w-[92px] flex-1 rounded-lg border border-danger/40 bg-danger/10 px-2 py-1.5 font-body text-[11px] font-semibold whitespace-nowrap text-danger max-lg:py-2.5 max-lg:text-xs"
            >
              Deny
            </button>
          ) : null}
          {canEdit ? (
            <button
              type="button"
              onClick={() => onEditClick?.(request.id)}
              className="min-w-[92px] flex-1 rounded-lg border border-border bg-surface px-2 py-1.5 font-body text-[11px] font-semibold max-lg:py-2.5 max-lg:text-xs whitespace-nowrap text-text transition-colors hover:border-secondary-accent/40 hover:bg-secondary-accent/8 hover:text-secondary-accent active:bg-secondary-accent/15"
            >
              Edit
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

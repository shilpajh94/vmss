import type { VisitRequestSummary } from '../../../domain/entities/visit-request-summary-schema'
import type { ApprovalWorkflowRule } from '../../../domain/entities/approval-workflow-rule-schema'
import { isReceptionCurrentStep, resolveTotalSteps } from '../../utils/approval-step-label'
import { CalendarClockIcon, InfoIcon, PencilIcon, UndoIcon, UserCheckIcon } from '../icons'

// An archived no-show can be rescheduled or edited; the API sends it back for
// re-approval when its date changes.
const RESCHEDULABLE_STATUSES = new Set(['submitted', 'approved', 'archived'])

export interface IconAction {
  label: string
  icon: typeof InfoIcon
  onClick: () => void
}

export interface InvitationActionHandlers {
  onRescheduleClick?: (id: string) => void
  onDelegateClick?: (id: string) => void
  onApproveAndDelegateClick?: (id: string) => void
  onApproveClick?: (id: string) => void
  onEditClick?: (id: string) => void
  // Checked-out invitations only get Edit (for the check-out time) when true.
  canEditCheckOutTime?: boolean
  onVisitorInfoClick?: (id: string) => void
  onRevertClick?: (id: string) => void
  onMoveToApproved?: (id: string) => void
  onMoveToDenied?: (id: string) => void
}

interface DeriveOptions extends InvitationActionHandlers {
  // Approve/Deny buttons are only for actionable (requested) invitations.
  isDraggable?: boolean
  isApproving?: boolean
  workflowRulesByCategory?: Record<string, ApprovalWorkflowRule[]>
}

export interface InvitationActions {
  approveAction?: { label: string; onClick: () => void }
  canTapDeny: boolean
  iconActions: IconAction[]
}

// Which actions an invitation offers, shared by the board card and the list
// row so the two views and their permission gating cannot drift apart. Each
// action appears only when its handler was passed (the page withholds
// handlers the user has no permission for).
export function deriveInvitationActions(request: VisitRequestSummary, options: DeriveOptions): InvitationActions {
  const {
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
  } = options
  const progress = request
  const isReceptionStep = isReceptionCurrentStep(progress.currentApprovalStep, progress.visitorCategoryId, workflowRulesByCategory ?? {})
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
  const canEdit =
    Boolean(onEditClick) && (RESCHEDULABLE_STATUSES.has(request.status) || (request.status === 'checked_out' && Boolean(canEditCheckOutTime)))
  const canRevert = Boolean(onRevertClick) && request.status === 'approved'
  // Until the category's live workflow rules have loaded,
  // `isReceptionStep`/`totalSteps` fall back to the step's own possibly-stale
  // `stepOrder`/`totalSteps` snapshot, which can misidentify Reception's step
  // as a later, freely-approvable one (`approve()` still hard-blocks this
  // case regardless — this just avoids the UI visibly allowing an action that
  // would immediately be rejected).
  const workflowRulesLoaded =
    !progress.currentApprovalStep || !progress.visitorCategoryId || workflowRulesByCategory?.[progress.visitorCategoryId] !== undefined
  const isActionable = isDraggable && !isApproving && workflowRulesLoaded
  // Reception's own step approves through its dedicated buttons, but it can
  // still deny.
  const canTapApprove = isActionable && !isReceptionApprovalStep && Boolean(onMoveToApproved)
  const canTapDeny = Boolean(isActionable && onMoveToDenied)

  const approveAction = canApproveAndDelegate
    ? { label: 'Approve & Delegate', onClick: () => onApproveAndDelegateClick?.(request.id) }
    : canApprove
      ? { label: 'Approve', onClick: () => onApproveClick?.(request.id) }
      : canTapApprove
        ? { label: 'Approve', onClick: () => onMoveToApproved?.(request.id) }
        : undefined

  const iconActions = [
    onVisitorInfoClick && { label: 'Visitor info', icon: InfoIcon, onClick: () => onVisitorInfoClick(request.id) },
    canReschedule && { label: 'Reschedule', icon: CalendarClockIcon, onClick: () => onRescheduleClick?.(request.id) },
    canEdit && { label: 'Edit', icon: PencilIcon, onClick: () => onEditClick?.(request.id) },
    canDelegate && { label: 'Delegate', icon: UserCheckIcon, onClick: () => onDelegateClick?.(request.id) },
    canRevert && { label: 'Revert approval', icon: UndoIcon, onClick: () => onRevertClick?.(request.id) },
  ].filter((action): action is IconAction => Boolean(action))

  return { approveAction, canTapDeny, iconActions }
}

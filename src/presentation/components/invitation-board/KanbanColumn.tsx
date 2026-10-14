import { useRef, useState } from 'react'
import type { VisitRequestSummary } from '../../../domain/entities/visit-request-summary-schema'
import type { InvitationDetail } from '../../../domain/entities/invitation-detail-schema'
import type { ApprovalWorkflowRule } from '../../../domain/entities/approval-workflow-rule-schema'
import { VisitRequestCard } from './VisitRequestCard'
import { UserIcon } from '../icons'
import { EmptyState } from '../ui/EmptyState'
import { Spinner } from '../ui/LoadingState'
import { BOARD_PAGE_SIZE } from '../../hooks/use-paged-board-columns'
import { useInfiniteScrollSentinel } from '../../hooks/use-infinite-scroll-sentinel'

const ACCENT_CLASSES = {
  requested: { border: 'border-l-info', tint: 'bg-info/8', text: 'text-info', dragOver: 'border-info bg-info/5 ring-info/40' },
  approved: { border: 'border-l-success', tint: 'bg-success/8', text: 'text-success', dragOver: 'border-success bg-success/5 ring-success/40' },
  checked_in: {
    border: 'border-l-secondary-accent',
    tint: 'bg-secondary-accent/8',
    text: 'text-secondary-accent',
    dragOver: 'border-secondary-accent bg-secondary-accent/5 ring-secondary-accent/40',
  },
  checked_out: {
    border: 'border-l-text-faint',
    tint: 'bg-text-faint/8',
    text: 'text-text-muted',
    dragOver: 'border-text-faint bg-text-faint/5 ring-text-faint/40',
  },
  denied: { border: 'border-l-danger', tint: 'bg-danger/8', text: 'text-danger', dragOver: 'border-danger bg-danger/5 ring-danger/40' },
} as const

interface KanbanColumnProps {
  status: keyof typeof ACCENT_CLASSES
  label: string
  requests: VisitRequestSummary[]
  /** Server total for this status - may exceed `requests.length` while pages remain unloaded. */
  total: number
  hasMore: boolean
  isLoadingMore: boolean
  loadMoreFailed: boolean
  onLoadMore: () => void
  emptyMessage: string
  onDrop?: (id: string) => void
  approvingId?: string
  invitationDetails?: Record<string, InvitationDetail>
  roleNameById?: Record<string, string>
  employeeNameById?: Record<string, string>
  workflowRulesByCategory?: Record<string, ApprovalWorkflowRule[]>
  onRescheduleClick?: (id: string) => void
  onDelegateClick?: (id: string) => void
  onApproveAndDelegateClick?: (id: string) => void
  onApproveClick?: (id: string) => void
  onEditClick?: (id: string) => void
  onVisitorInfoClick?: (id: string) => void
  onCheckOutClick?: (id: string) => void
  onRevertClick?: (id: string) => void
  onMoveToApproved?: (id: string) => void
  onMoveToDenied?: (id: string) => void
}

export function KanbanColumn({
  status,
  label,
  requests,
  total,
  hasMore,
  isLoadingMore,
  loadMoreFailed,
  onLoadMore,
  emptyMessage,
  onDrop,
  approvingId,
  invitationDetails,
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
}: KanbanColumnProps) {
  const accent = ACCENT_CLASSES[status]
  const [isDragOver, setIsDragOver] = useState(false)
  const scrollAreaRef = useRef<HTMLDivElement>(null)
  const sentinelRef = useRef<HTMLDivElement>(null)

  useInfiniteScrollSentinel(sentinelRef, scrollAreaRef, onLoadMore, {
    enabled: hasMore && !isLoadingMore && !loadMoreFailed,
    watchKey: requests.length,
  })

  return (
    <div
      className="flex min-w-0 flex-1 flex-col gap-3 lg:min-h-0 lg:min-w-[170px]"
      onDragOver={
        onDrop
          ? (event) => {
              event.preventDefault()
              setIsDragOver(true)
            }
          : undefined
      }
      onDragLeave={onDrop ? () => setIsDragOver(false) : undefined}
      onDrop={
        onDrop
          ? (event) => {
              event.preventDefault()
              setIsDragOver(false)
              const id = event.dataTransfer.getData('text/plain')
              if (id) onDrop(id)
            }
          : undefined
      }
    >
      {/* Outside the scroll area below, so it stays put however far the cards scroll (desktop). */}
      <div className={`flex w-full shrink-0 items-center justify-between rounded-[10px] border-l-4 px-4 py-2 ${accent.border} ${accent.tint}`}>
        <p className="font-display text-base font-bold text-text">{label}</p>
        <span className={`rounded-full border border-border bg-surface px-2 py-0.5 font-body text-xs font-bold ${accent.text}`}>{total}</span>
      </div>

      {requests.length === 0 ? (
        <EmptyState
          message={emptyMessage}
          icon={<UserIcon className="size-4 text-text-muted" />}
          className={`h-40 w-full rounded-xl border border-dashed p-6 transition-colors ${
            isDragOver ? accent.dragOver : 'border-[#cbd5e1]'
          }`}
        />
      ) : (
        <div
          ref={scrollAreaRef}
          className={`scrollbar-thin flex w-full flex-col gap-2 rounded-xl p-1 transition-colors lg:min-h-0 lg:flex-1 lg:overflow-y-auto ${isDragOver ? `ring-2 ${accent.dragOver}` : ''}`}
        >
          {requests.map((request) => (
            <VisitRequestCard
              key={request.id}
              request={request}
              isDraggable={status === 'requested'}
              isApproving={approvingId === request.id}
              detail={invitationDetails?.[request.id]}
              roleNameById={roleNameById}
              employeeNameById={employeeNameById}
              workflowRulesByCategory={workflowRulesByCategory}
              onRescheduleClick={onRescheduleClick}
              onDelegateClick={onDelegateClick}
              onApproveAndDelegateClick={onApproveAndDelegateClick}
              onApproveClick={onApproveClick}
              onEditClick={onEditClick}
              onVisitorInfoClick={onVisitorInfoClick}
              onCheckOutClick={onCheckOutClick}
              onRevertClick={onRevertClick}
              onMoveToApproved={onMoveToApproved}
              onMoveToDenied={onMoveToDenied}
            />
          ))}
          <div ref={sentinelRef} aria-hidden className="h-px shrink-0" />
          {isLoadingMore ? (
            <div role="status" className="flex shrink-0 items-center justify-center gap-2 py-3 font-body text-xs text-text-muted">
              <Spinner className="size-4" />
              Loading more…
            </div>
          ) : loadMoreFailed ? (
            <div className="flex shrink-0 flex-col items-center gap-2 py-3 text-center">
              <p className="font-body text-xs text-danger">Couldn't load more visits.</p>
              <button
                type="button"
                onClick={onLoadMore}
                className="min-h-9 rounded-lg border border-border bg-surface px-3 font-body text-xs font-semibold text-text"
              >
                Retry
              </button>
            </div>
          ) : !hasMore && requests.length > BOARD_PAGE_SIZE ? (
            <p className="shrink-0 py-3 text-center font-body text-xs text-text-muted">All {requests.length} shown</p>
          ) : null}
        </div>
      )}
    </div>
  )
}

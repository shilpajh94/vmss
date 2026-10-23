import { useRef, useState } from 'react'
import type { VisitRequestSummary } from '../../../domain/entities/visit-request-summary-schema'
import type { ApprovalWorkflowRule } from '../../../domain/entities/approval-workflow-rule-schema'
import { VisitRequestCard } from './VisitRequestCard'
import { UserIcon } from '../icons'
import { EmptyState } from '../ui/EmptyState'
import { Skeleton } from '../ui/Skeleton'
import { BOARD_PAGE_SIZE } from '../../hooks/use-paged-board-columns'
import { useInfiniteScrollSentinel } from '../../hooks/use-infinite-scroll-sentinel'

export const ACCENT_CLASSES = {
  requested: { border: 'border-l-info', tint: 'bg-info/8', text: 'text-info', dragOver: 'border-info bg-info/5 ring-info/40' },
  approved: { border: 'border-l-success', tint: 'bg-success/8', text: 'text-success-text', dragOver: 'border-success bg-success/5 ring-success/40' },
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
  archived: { border: 'border-l-warning', tint: 'bg-warning/8', text: 'text-warning', dragOver: 'border-warning bg-warning/5 ring-warning/40' },
} as const

// Shared with ClosedStatusesColumn so every desktop column sizes the same way.
export const BOARD_COLUMN_SIZING = 'flex min-w-0 flex-1 flex-col lg:min-h-0 lg:min-w-[240px] lg:basis-0'

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
  /** Rendered inside the Closed column's tab panel, which owns the header and sizing. */
  embedded?: boolean
  onDrop?: (id: string) => void
  approvingId?: string
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
  embedded = false,
  onDrop,
  approvingId,
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
      // Columns share the board evenly but stop at 240px; past that the board
      // scrolls sideways instead of truncating cards (staff-dashboard "Board
      // columns keep a readable minimum width").
      className={embedded ? 'flex min-h-0 flex-1 flex-col' : `${BOARD_COLUMN_SIZING} gap-3`}
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
      {embedded ? null : (
        // Outside the scroll area below, so it stays put however far the cards scroll (desktop).
        <div className={`flex w-full shrink-0 items-center justify-between gap-2 rounded-[10px] border-l-4 px-4 py-2 ${accent.border} ${accent.tint}`}>
          <p className="min-w-0 truncate font-display text-base font-bold text-text">{label}</p>
          <span className={`shrink-0 rounded-full border border-border bg-surface px-2 py-0.5 font-body text-xs font-bold ${accent.text}`}>{total}</span>
        </div>
      )}

      {requests.length === 0 ? (
        <EmptyState
          message={emptyMessage}
          icon={<UserIcon className="size-4 text-text-muted" />}
          className={`h-40 w-full rounded-xl border border-dashed p-6 transition-colors ${
            isDragOver ? accent.dragOver : 'border-border-strong'
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
            // A card-shaped placeholder at the column's foot, where the next
            // page's cards will land (async-ui-states skeletons).
            <div role="status" aria-label="Loading more…" className="flex shrink-0 flex-col gap-3 rounded-xl border border-border bg-surface p-4">
              <div className="flex items-center gap-3">
                <Skeleton className="size-9 shrink-0 rounded-full" />
                <div className="flex min-w-0 flex-1 flex-col gap-1.5">
                  <Skeleton className="h-3.5 w-2/3" />
                  <Skeleton className="h-3 w-1/2" />
                </div>
              </div>
              <Skeleton className="h-3 w-3/5" />
            </div>
          ) : loadMoreFailed ? (
            <div className="flex shrink-0 flex-col items-center gap-2 py-3 text-center">
              <p className="font-body text-xs text-danger">Couldn't load more visits.</p>
              <button
                type="button"
                onClick={onLoadMore}
                className="min-h-10 rounded-lg border border-border bg-surface px-3 font-body text-xs font-semibold text-text lg:min-h-9"
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

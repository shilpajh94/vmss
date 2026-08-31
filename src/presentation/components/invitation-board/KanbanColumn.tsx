import { useState } from 'react'
import type { VisitRequestSummary } from '../../../domain/entities/visit-request-summary-schema'
import type { InvitationDetail } from '../../../domain/entities/invitation-detail-schema'
import { VisitRequestCard } from './VisitRequestCard'
import { UserIcon } from '../icons'
import { EmptyState } from '../ui/EmptyState'

const ACCENT_CLASSES = {
  requested: { border: 'border-l-info', tint: 'bg-info/8', text: 'text-info', dragOver: 'border-info bg-info/5 ring-info/40' },
  approved: { border: 'border-l-success', tint: 'bg-success/8', text: 'text-success', dragOver: 'border-success bg-success/5 ring-success/40' },
  checked_in: {
    border: 'border-l-secondary-accent',
    tint: 'bg-secondary-accent/8',
    text: 'text-secondary-accent',
    dragOver: 'border-secondary-accent bg-secondary-accent/5 ring-secondary-accent/40',
  },
  denied: { border: 'border-l-danger', tint: 'bg-danger/8', text: 'text-danger', dragOver: 'border-danger bg-danger/5 ring-danger/40' },
} as const

interface KanbanColumnProps {
  status: keyof typeof ACCENT_CLASSES
  label: string
  requests: VisitRequestSummary[]
  emptyMessage: string
  onDrop?: (id: string) => void
  approvingId?: string
  expandedId?: string
  onToggleExpand?: (id: string) => void
  invitationDetails?: Record<string, InvitationDetail>
  loadingDetailId?: string
  roleNameById?: Record<string, string>
  employeeNameById?: Record<string, string>
  onReschedule?: (id: string, preferredVisitDate: string, preferredVisitTime: string) => void
  reschedulingId?: string
}

export function KanbanColumn({
  status,
  label,
  requests,
  emptyMessage,
  onDrop,
  approvingId,
  expandedId,
  onToggleExpand,
  invitationDetails,
  loadingDetailId,
  roleNameById,
  employeeNameById,
  onReschedule,
  reschedulingId,
}: KanbanColumnProps) {
  const accent = ACCENT_CLASSES[status]
  const [isDragOver, setIsDragOver] = useState(false)

  return (
    <div
      className="flex h-full min-w-0 flex-1 flex-col gap-4"
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
      <div className={`flex w-full items-center justify-between rounded-[10px] border-l-4 px-4 py-3 ${accent.border} ${accent.tint}`}>
        <p className="font-display text-base font-bold text-text">{label}</p>
        <span className={`rounded-full border border-border bg-surface px-2 py-0.5 font-body text-xs font-bold ${accent.text}`}>{requests.length}</span>
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
          className={`flex w-full flex-col gap-3 rounded-xl p-1 transition-colors ${isDragOver ? `ring-2 ${accent.dragOver}` : ''}`}
        >
          {requests.map((request) => (
            <VisitRequestCard
              key={request.id}
              request={request}
              isDraggable={status === 'requested'}
              isApproving={approvingId === request.id}
              isExpanded={expandedId === request.id}
              onToggleExpand={onToggleExpand}
              detail={invitationDetails?.[request.id]}
              isLoadingDetail={loadingDetailId === request.id}
              roleNameById={roleNameById}
              employeeNameById={employeeNameById}
              onReschedule={onReschedule}
              isRescheduling={reschedulingId === request.id}
            />
          ))}
        </div>
      )}
    </div>
  )
}

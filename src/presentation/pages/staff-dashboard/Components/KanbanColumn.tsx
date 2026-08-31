import { useState } from 'react'
import type { VisitRequestSummary } from '../../../../domain/entities/visit-request-summary-schema'
import { VisitRequestCard } from './VisitRequestCard'
import { UserIcon } from '../../../components/icons'
import { EmptyState } from '../../../components/ui/EmptyState'

const ACCENT_CLASSES = {
  requested: { border: 'border-l-info', tint: 'bg-info/8', text: 'text-info' },
  approved: { border: 'border-l-success', tint: 'bg-success/8', text: 'text-success' },
  checked_in: { border: 'border-l-secondary-accent', tint: 'bg-secondary-accent/8', text: 'text-secondary-accent' },
  denied: { border: 'border-l-danger', tint: 'bg-danger/8', text: 'text-danger' },
} as const

interface KanbanColumnProps {
  status: keyof typeof ACCENT_CLASSES
  label: string
  requests: VisitRequestSummary[]
  emptyMessage: string
  onDropApprove?: (id: string) => void
  approvingId?: string
}

export function KanbanColumn({ status, label, requests, emptyMessage, onDropApprove, approvingId }: KanbanColumnProps) {
  const accent = ACCENT_CLASSES[status]
  const [isDragOver, setIsDragOver] = useState(false)

  return (
    <div
      className="flex h-full min-w-0 flex-1 flex-col gap-4"
      onDragOver={
        onDropApprove
          ? (event) => {
              event.preventDefault()
              setIsDragOver(true)
            }
          : undefined
      }
      onDragLeave={onDropApprove ? () => setIsDragOver(false) : undefined}
      onDrop={
        onDropApprove
          ? (event) => {
              event.preventDefault()
              setIsDragOver(false)
              const id = event.dataTransfer.getData('text/plain')
              if (id) onDropApprove(id)
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
            isDragOver ? 'border-success bg-success/5' : 'border-[#cbd5e1]'
          }`}
        />
      ) : (
        <div
          className={`flex w-full flex-col gap-3 rounded-xl p-1 transition-colors ${isDragOver ? 'bg-success/5 ring-2 ring-success/40' : ''}`}
        >
          {requests.map((request) => (
            <VisitRequestCard
              key={request.id}
              request={request}
              isDraggable={status === 'requested'}
              isApproving={approvingId === request.id}
            />
          ))}
        </div>
      )}
    </div>
  )
}

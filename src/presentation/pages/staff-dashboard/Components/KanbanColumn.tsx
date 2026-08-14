import type { VisitRequestSummary } from '../../../../domain/entities/visit-request-summary-schema'
import { VisitRequestCard } from './VisitRequestCard'
import { UserIcon } from './icons'

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
}

export function KanbanColumn({ status, label, requests, emptyMessage }: KanbanColumnProps) {
  const accent = ACCENT_CLASSES[status]

  return (
    <div className="flex h-full min-w-0 flex-1 flex-col gap-4">
      <div className={`flex w-full items-center justify-between rounded-[10px] border-l-4 px-4 py-3 ${accent.border} ${accent.tint}`}>
        <p className="font-display text-base font-bold text-text">{label}</p>
        <span className={`rounded-full border border-border bg-surface px-2 py-0.5 font-body text-xs font-bold ${accent.text}`}>{requests.length}</span>
      </div>

      {requests.length === 0 ? (
        <div className="flex h-40 w-full flex-col items-center justify-center gap-3 rounded-xl border border-dashed border-[#cbd5e1] p-6">
          <span className="flex size-8 items-center justify-center rounded-full bg-bg">
            <UserIcon className="size-4 text-text-muted" />
          </span>
          <p className="text-center font-body text-xs font-medium text-text-muted">{emptyMessage}</p>
        </div>
      ) : (
        <div className="flex w-full flex-col gap-3">
          {requests.map((request) => (
            <VisitRequestCard key={request.id} request={request} />
          ))}
        </div>
      )}
    </div>
  )
}

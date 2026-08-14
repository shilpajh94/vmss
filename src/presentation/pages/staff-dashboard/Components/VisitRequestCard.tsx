import type { VisitRequestSummary } from '../../../../domain/entities/visit-request-summary-schema'
import { CalendarClockIcon } from '../../../components/icons'

const AVATAR_TINTS = ['#dbeafe', '#ffe4e6', '#d1fae5', '#fef3c7', '#f3e8ff', '#fee2e2']

function avatarTintFor(reqId: string): string {
  const hash = reqId.split('').reduce((sum, char) => sum + char.charCodeAt(0), 0)
  return AVATAR_TINTS[hash % AVATAR_TINTS.length]
}

interface VisitRequestCardProps {
  request: VisitRequestSummary
}

export function VisitRequestCard({ request }: VisitRequestCardProps) {
  return (
    <div className="flex w-full flex-col gap-3 rounded-xl border border-border bg-surface p-4 drop-shadow-[0px_4px_4px_rgba(15,23,42,0.03)]">
      <div className="flex w-full items-center justify-between">
        <span
          className="flex size-8 shrink-0 items-center justify-center rounded-full font-display text-xs font-bold text-text"
          style={{ backgroundColor: avatarTintFor(request.reqId) }}
        >
          {request.visitorInitials}
        </span>
        <span className="font-body text-[11px] font-semibold whitespace-nowrap text-text-faint">{request.reqId}</span>
      </div>

      <div className="flex w-full flex-col gap-1">
        <p className="truncate font-body text-sm font-bold text-text">{request.visitorName}</p>
        <div className="flex items-center gap-1 font-body text-xs">
          <span className="text-text-muted">Host:</span>
          <span className="font-medium text-text">{request.hostName}</span>
        </div>
      </div>

      <div className="h-px w-full bg-border-subtle" />

      <div className="flex w-full items-center gap-1.5">
        <CalendarClockIcon className="size-3 shrink-0 text-text-faint" />
        <span className="font-body text-[11px] whitespace-nowrap text-text-faint">{request.scheduledAt}</span>
      </div>
    </div>
  )
}

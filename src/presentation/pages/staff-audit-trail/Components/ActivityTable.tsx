import type { AuditLogEntry } from '../../../../domain/entities/audit-log-entry-schema'
import { EmptyState } from '../../../components/ui/EmptyState'
import { StatusPill } from './StatusPill'

interface ActivityTableProps {
  entries: AuditLogEntry[]
}

const COLUMN_LABELS = ['Timestamp', 'Activity', 'Visitor', 'Description', 'Zone', 'Method', 'Status']

export function ActivityTable({ entries }: ActivityTableProps) {
  if (entries.length === 0) {
    return (
      <EmptyState
        message="No activity matches the current filters."
        className="w-full flex-1 rounded-xl border border-border bg-surface p-12"
      />
    )
  }

  return (
    <div className="flex w-full flex-1 flex-col overflow-hidden rounded-xl border border-border bg-surface">
      <div className="flex w-full items-center gap-3 border-b border-border bg-border-subtle px-4 py-3">
        <p className="w-[140px] shrink-0 font-body text-xs font-bold text-text-muted">{COLUMN_LABELS[0]}</p>
        <p className="w-[120px] shrink-0 font-body text-xs font-bold text-text-muted">{COLUMN_LABELS[1]}</p>
        <p className="w-[160px] shrink-0 font-body text-xs font-bold text-text-muted">{COLUMN_LABELS[2]}</p>
        <p className="min-w-0 flex-1 font-body text-xs font-bold text-text-muted">{COLUMN_LABELS[3]}</p>
        <p className="w-[100px] shrink-0 font-body text-xs font-bold text-text-muted">{COLUMN_LABELS[4]}</p>
        <p className="w-[90px] shrink-0 font-body text-xs font-bold text-text-muted">{COLUMN_LABELS[5]}</p>
        <p className="w-[120px] shrink-0 font-body text-xs font-bold text-text-muted">{COLUMN_LABELS[6]}</p>
      </div>

      {entries.map((entry, index) => (
        <div
          key={entry.id}
          className={`flex w-full items-center gap-3 px-4 py-3 ${index < entries.length - 1 ? 'border-b border-border' : ''}`}
        >
          <p className="w-[140px] shrink-0 font-body text-[13px] text-text">{entry.timestamp}</p>
          <p className="w-[120px] shrink-0 font-body text-[13px] font-semibold text-text">{entry.activity}</p>
          <p className="w-[160px] shrink-0 font-body text-[13px] text-text">{entry.visitorName}</p>
          <p className="min-w-0 flex-1 truncate font-body text-[13px] text-text-muted">{entry.description}</p>
          <p className="w-[100px] shrink-0 font-body text-[13px] text-text">{entry.zone}</p>
          <p className="w-[90px] shrink-0 font-body text-[13px] text-text">{entry.method}</p>
          <div className="flex w-[120px] shrink-0 items-center">
            <StatusPill status={entry.status} />
          </div>
        </div>
      ))}
    </div>
  )
}

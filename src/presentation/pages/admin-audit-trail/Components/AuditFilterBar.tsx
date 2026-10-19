import { CalendarIcon, SlidersIcon } from '../../../components/icons'
import { PendingButton } from '../../../components/ui/PendingButton'
import { ACTIVITY_TYPE_OPTIONS, DATE_RANGE_OPTIONS } from '../types'
import { DropdownFilter } from '../../../components/ui/DropdownFilter'
import type { AuditReportFormat } from '../../../../data/repositories/audit-trail-repository'

interface AuditFilterBarProps {
  dateRange: string
  onDateRangeChange: (value: string) => void
  activityType: string
  onActivityTypeChange: (value: string) => void
  downloadingFormat: AuditReportFormat | undefined
  onDownload: (format: AuditReportFormat) => void
}

export function AuditFilterBar({
  dateRange,
  onDateRangeChange,
  activityType,
  onActivityTypeChange,
  downloadingFormat,
  onDownload,
}: AuditFilterBarProps) {
  return (
    <div className="flex w-full items-center gap-3 rounded-xl border border-border bg-surface p-4">
      <DropdownFilter icon={CalendarIcon} value={dateRange} options={DATE_RANGE_OPTIONS} onChange={onDateRangeChange} ariaLabel="Date range" />
      <DropdownFilter icon={SlidersIcon} value={activityType} options={ACTIVITY_TYPE_OPTIONS} onChange={onActivityTypeChange} ariaLabel="Activity type" />

      <div className="ml-auto flex items-center gap-2">
        <PendingButton
          pending={downloadingFormat === 'csv'}
          pendingLabel="Preparing…"
          disabled={downloadingFormat !== undefined}
          onClick={() => onDownload('csv')}
          className="rounded-lg border border-border bg-surface px-3.5 py-2 font-body text-[13px] font-semibold text-text enabled:hover:bg-border-subtle disabled:opacity-60"
        >
          Download CSV
        </PendingButton>
        <PendingButton
          pending={downloadingFormat === 'pdf'}
          pendingLabel="Preparing…"
          disabled={downloadingFormat !== undefined}
          onClick={() => onDownload('pdf')}
          className="rounded-lg border border-border bg-surface px-3.5 py-2 font-body text-[13px] font-semibold text-text enabled:hover:bg-border-subtle disabled:opacity-60"
        >
          Download PDF
        </PendingButton>
      </div>
    </div>
  )
}
